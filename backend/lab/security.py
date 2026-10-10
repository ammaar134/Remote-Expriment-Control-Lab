"""Explicit local access or one authenticated operator behind a HTTPS proxy."""

import hashlib
import hmac
import json
import os
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

LOCAL_ORIGINS = {
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
MUTATIONS = {"POST", "PUT", "PATCH", "DELETE"}
SESSION_COOKIE = "__Host-lab_session"
SESSION_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class AccessSettings:
    mode: str
    origin: str = ""
    username: str = ""
    password: str = field(default="", repr=False)
    session_secret: str = field(default="", repr=False)

    @classmethod
    def from_environment(cls):
        mode = os.getenv("LAB_MODE", "local")
        if mode == "local":
            return cls(mode)
        if mode != "hosted":
            raise RuntimeError("LAB_MODE must be local or hosted")
        origin = os.getenv("LAB_PUBLIC_ORIGIN", "")
        if not origin and os.getenv("RENDER_EXTERNAL_HOSTNAME"):
            origin = "https://" + os.environ["RENDER_EXTERNAL_HOSTNAME"]
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.netloc != parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in origin
        ):
            raise RuntimeError("Hosted mode requires a HTTPS LAB_PUBLIC_ORIGIN without path or port")
        username = os.getenv("LAB_USERNAME", "operator")
        password = os.getenv("LAB_PASSWORD", "")
        if not username or ":" in username or not username.isascii() or not 12 <= len(password) <= 1024:
            raise RuntimeError("Hosted mode requires a username and a password of 12 to 1024 characters")
        session_secret = os.getenv("LAB_SESSION_SECRET", "")
        if len(session_secret) < 32:
            raise RuntimeError("Hosted mode requires a random LAB_SESSION_SECRET of at least 32 characters")
        if int(os.getenv("WEB_CONCURRENCY", "1")) != 1:
            raise RuntimeError("Run exactly one API worker")
        return cls(mode, origin, username, password, session_secret)

    @property
    def hosts(self) -> list[str]:
        if self.mode == "local":
            return ["localhost", "127.0.0.1", "lab", "testserver"]
        return [urlsplit(self.origin).hostname or "", "localhost", "127.0.0.1"]

    def credentials_match(self, username: str, password: str) -> bool:
        # Hashing fixes lengths before constant-time comparison, including Unicode passwords.
        valid_user = hmac.compare_digest(
            hashlib.sha256(username.encode()).digest(), hashlib.sha256(self.username.encode()).digest()
        )
        valid_password = hmac.compare_digest(
            hashlib.sha256(password.encode()).digest(), hashlib.sha256(self.password.encode()).digest()
        )
        return valid_user & valid_password

    def signature(self, payload: str) -> str:
        # Credential rotation invalidates old sessions; a separate random key keeps
        # a human-sized password from becoming the cookie signing key.
        key = hmac.digest(
            self.session_secret.encode(), (self.username + "\0" + self.password).encode(), "sha256"
        )
        return hmac.new(key, payload.encode(), "sha256").hexdigest()

    def new_session(self) -> str:
        payload = f"v1.{int(time.time()) + SESSION_SECONDS}.{secrets.token_hex(16)}"
        return payload + "." + self.signature(payload)

    def authenticated(self, token: str) -> bool:
        if len(token) > 256:
            return False
        try:
            version, expiry, nonce, signature = token.split(".")
            valid_time = time.time() < int(expiry) <= time.time() + SESSION_SECONDS
        except ValueError:
            return False
        payload = f"{version}.{expiry}.{nonce}"
        return (
            version == "v1"
            and len(nonce) == 32
            and valid_time
            and hmac.compare_digest(self.signature(payload).encode(), signature.encode())
        )


class AccessControls(BaseHTTPMiddleware):
    def __init__(self, app, settings: AccessSettings):
        super().__init__(app)
        self.settings = settings
        # One bounded limiter per process. Entries expire after a minute; a full
        # table rejects new sources rather than evicting and bypassing a limit.
        self.attempts: OrderedDict[str, tuple[float, int]] = OrderedDict()

    async def dispatch(self, request: Request, call_next):
        response = self.reject(request)
        if response is None:
            response = await self.auth_response(request)
        if response is None:
            response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
                ),
            }
        )
        if self.settings.mode == "hosted":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    async def auth_response(self, request: Request):
        path = request.url.path
        if path not in {"/auth/session", "/auth/login", "/auth/logout"}:
            return None
        if request.method != ("GET" if path == "/auth/session" else "POST"):
            return JSONResponse({"detail": "Method not allowed"}, status_code=405)
        local = self.settings.mode == "local"
        if path == "/auth/session":
            return JSONResponse(
                {
                    "authenticated": local
                    or self.settings.authenticated(request.cookies.get(SESSION_COOKIE, "")),
                    "mode": self.settings.mode,
                }
            )
        if path == "/auth/logout":
            response = JSONResponse({"authenticated": local, "mode": self.settings.mode})
            response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="strict")
            return response
        now = time.monotonic()
        while self.attempts and next(iter(self.attempts.values()))[0] <= now - 60:
            self.attempts.popitem(last=False)
        client = request.client.host if request.client else "unknown"
        since, count = self.attempts.get(client, (now, 0))
        if count >= 5 or (client not in self.attempts and len(self.attempts) >= 1024):
            return JSONResponse(
                {"detail": "Too many sign-in attempts. Wait one minute, then try again."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        # Count before reading the body so simultaneous attempts cannot bypass the limit.
        self.attempts[client] = (since, count + 1)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return JSONResponse({"detail": "Sign-in request is too large"}, status_code=413)
        try:
            credentials = json.loads(body)
            username, password = credentials["username"], credentials["password"]
            valid = (
                isinstance(username, str)
                and isinstance(password, str)
                and len(username) <= 128
                and len(password) <= 1024
                and self.settings.credentials_match(username, password)
            )
        except (ValueError, KeyError, TypeError, UnicodeError):
            return JSONResponse({"detail": "Enter a username and password"}, status_code=400)
        if not valid:
            return JSONResponse({"detail": "Username or password is incorrect"}, status_code=401)
        self.attempts.pop(client, None)
        response = JSONResponse({"authenticated": True, "mode": self.settings.mode})
        response.set_cookie(
            SESSION_COOKIE,
            self.settings.new_session(),
            max_age=SESSION_SECONDS,
            secure=True,
            httponly=True,
            samesite="strict",
        )
        return response

    def reject(self, request: Request):
        hosted = self.settings.mode == "hosted"
        public_shell = request.method == "GET" and (
            request.url.path in {"/", "/index.html", "/favicon.svg"}
            or request.url.path.startswith(("/assets/", "/fonts/"))
        )
        # Platform probes learn only process/startup health, never device or saved data.
        if request.method == "GET" and request.url.path == "/healthz":
            return None
        if hosted:
            if request.url.scheme != "https":
                return JSONResponse({"detail": "HTTPS is required"}, status_code=403)
            public = public_shell or (request.method == "GET" and request.url.path == "/auth/session")
            auth_action = request.url.path in {"/auth/login", "/auth/logout"}
            if (
                not public
                and not auth_action
                and not self.settings.authenticated(request.cookies.get(SESSION_COOKIE, ""))
            ):
                return JSONResponse(
                    {"detail": "Operator sign-in required"},
                    status_code=401,
                )
        origin = request.headers.get("origin")
        allowed = {self.settings.origin} if hosted else LOCAL_ORIGINS
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
        if hosted and (
            (not public_shell and request.headers.get("sec-fetch-site") == "cross-site")
            or (request.method in MUTATIONS and origin != self.settings.origin)
        ):
            return JSONResponse({"detail": "A same-origin request is required"}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH"}:
            length = request.headers.get("content-length")
            if not length or not length.isdigit() or int(length) > 65_536:
                return JSONResponse({"detail": "A body of at most 64 KiB is required"}, status_code=413)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "JSON is required"}, status_code=415)
        return None
