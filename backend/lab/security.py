"""Explicit local access or one authenticated operator behind a HTTPS proxy."""

import base64
import binascii
import hashlib
import hmac
import os
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


@dataclass(frozen=True)
class AccessSettings:
    mode: str
    origin: str = ""
    username: str = ""
    password: str = field(default="", repr=False)

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
        if not username or ":" in username or not username.isascii() or len(password) < 32:
            raise RuntimeError(
                "Hosted mode requires a username and a random password of at least 32 characters"
            )
        if int(os.getenv("WEB_CONCURRENCY", "1")) != 1:
            raise RuntimeError("Run exactly one API worker")
        return cls(mode, origin, username, password)

    @property
    def hosts(self) -> list[str]:
        if self.mode == "local":
            return ["localhost", "127.0.0.1", "lab", "testserver"]
        return [urlsplit(self.origin).hostname or "", "localhost", "127.0.0.1"]

    def authenticated(self, header: str) -> bool:
        try:
            scheme, encoded = header.split(" ", 1)
            if scheme.lower() != "basic" or len(encoded) > 2048:
                return False
            decoded = base64.b64decode(encoded, validate=True)
            username, password = decoded.split(b":", 1)
        except (ValueError, binascii.Error):
            return False
        # Hashing fixes lengths before constant-time comparison, including Unicode passwords.
        valid_user = hmac.compare_digest(
            hashlib.sha256(username).digest(), hashlib.sha256(self.username.encode()).digest()
        )
        valid_password = hmac.compare_digest(
            hashlib.sha256(password).digest(), hashlib.sha256(self.password.encode()).digest()
        )
        return valid_user & valid_password


class AccessControls(BaseHTTPMiddleware):
    def __init__(self, app, settings: AccessSettings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        response = self.reject(request)
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

    def reject(self, request: Request):
        hosted = self.settings.mode == "hosted"
        # Platform probes learn only process/startup health, never device or saved data.
        if request.method == "GET" and request.url.path == "/healthz":
            return None
        if hosted:
            if request.url.scheme != "https":
                return JSONResponse({"detail": "HTTPS is required"}, status_code=403)
            if not self.settings.authenticated(request.headers.get("authorization", "")):
                return JSONResponse(
                    {"detail": "Operator sign-in required"},
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Experiment Lab", charset="UTF-8"'},
                )
        origin = request.headers.get("origin")
        allowed = {self.settings.origin} if hosted else LOCAL_ORIGINS
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
        if hosted and (
            request.headers.get("sec-fetch-site") == "cross-site"
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
