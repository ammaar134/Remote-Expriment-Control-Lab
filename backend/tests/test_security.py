import secrets
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lab.security import SESSION_COOKIE, SESSION_SECONDS, AccessControls, AccessSettings

ORIGIN = "https://lab.example.com"


@pytest.fixture
def protected():
    settings = AccessSettings(
        "hosted", ORIGIN, "operator", secrets.token_urlsafe(9), secrets.token_urlsafe(32)
    )
    app = FastAPI()
    app.add_middleware(AccessControls, settings=settings)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.hosts)

    @app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
    def example(path: str):
        return {"served": path}

    with TestClient(app, base_url=ORIGIN) as client:
        yield client, settings


def login(client, settings):
    return client.post(
        "/auth/login",
        json={"username": settings.username, "password": settings.password},
        headers={"Origin": ORIGIN},
    )


@pytest.mark.parametrize("path", ["/api/health", "/api/runs", "/api/device", "/docs", "/openapi.json"])
def test_data_and_controls_require_cookie_without_browser_challenges(protected, path):
    client, settings = protected
    response = client.get(path)
    assert response.status_code == 401
    assert "www-authenticate" not in response.headers
    assert client.get(path, auth=("operator", settings.password)).status_code == 401
    assert login(client, settings).status_code == 200
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/", "/index.html", "/assets/index.js", "/fonts/Manrope.ttf"])
def test_sign_in_shell_stays_available_without_authentication(protected, path):
    client, _ = protected
    response = client.get(path)
    assert response.status_code == 200
    assert "www-authenticate" not in response.headers
    assert client.get("/auth/session").json() == {"authenticated": False, "mode": "hosted"}
    assert client.get(path, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


def test_cookie_flags_refresh_and_logout(protected):
    client, settings = protected
    response = login(client, settings)
    cookie = response.headers["set-cookie"]
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/", f"Max-Age={SESSION_SECONDS}"):
        assert flag in cookie
    assert "Domain=" not in cookie
    for _ in range(4):
        assert client.get("/").status_code == 200
        assert client.get("/auth/session").json()["authenticated"]
        assert client.get("/api/runs").status_code == 200
    assert client.post("/auth/logout", json={}, headers={"Origin": ORIGIN}).status_code == 200
    assert not client.get("/auth/session").json()["authenticated"]
    assert client.get("/api/runs").status_code == 401


def test_failed_sign_in_limit_expires_and_has_no_native_prompt(protected, monkeypatch):
    client, settings = protected
    now = [100.0]
    monkeypatch.setattr("lab.security.time.monotonic", lambda: now[0])
    for _ in range(5):
        response = login(client, replace(settings, password="wrong"))
        assert response.status_code == 401
        assert "www-authenticate" not in response.headers
    response = login(client, settings)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    now[0] += 61
    assert login(client, settings).status_code == 200


def test_session_expiry_tampering_and_credential_rotation(protected, monkeypatch):
    client, settings = protected
    monkeypatch.setattr("lab.security.time.time", lambda: 1000)
    token = settings.new_session()
    assert settings.authenticated(token)
    assert replace(settings).authenticated(token), "Same settings survive a process restart"
    assert not replace(settings, password=secrets.token_urlsafe(12)).authenticated(token)
    assert not replace(settings, session_secret=secrets.token_urlsafe(32)).authenticated(token)
    for broken in ("garbage", token + "x", token.replace("v1", "v2"), "v1.nope.nonce.signature", "x" * 300):
        assert not settings.authenticated(broken)
    monkeypatch.setattr("lab.security.time.time", lambda: 1000 + SESSION_SECONDS)
    assert not settings.authenticated(token)
    client.cookies.set(SESSION_COOKIE, token)
    response = client.get("/api/runs")
    assert response.status_code == 401
    assert "www-authenticate" not in response.headers


def test_https_host_origin_and_request_body_guards(protected):
    client, settings = protected
    assert client.get("http://localhost/healthz").status_code == 200
    assert client.get("http://localhost/").status_code == 403
    assert client.get("https://untrusted.example/api/runs").status_code == 400
    credentials = {"username": settings.username, "password": settings.password}
    assert client.post("/auth/login", json=credentials).status_code == 403
    assert (
        client.post("/auth/login", json=credentials, headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert login(client, settings).status_code == 200
    assert client.post("/api/runs", json={}).status_code == 403
    assert client.post("/auth/logout", json={}).status_code == 403
    assert client.get("/api/runs", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    headers = {"Origin": ORIGIN}
    assert client.post("/api/runs", content="text", headers=headers).status_code == 415
    assert client.post("/api/runs", json={"large": "x" * 65536}, headers=headers).status_code == 413
    assert client.post("/auth/login", json={"large": "x" * 4096}, headers=headers).status_code == 413
    response = client.post("/api/runs", json={}, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "max-age=" in response.headers["strict-transport-security"]


@pytest.mark.parametrize("body", ["not-json", "[]", "{}", '{"username":null,"password":5}'])
def test_invalid_login_body_is_rejected(protected, body):
    client, _ = protected
    response = client.post(
        "/auth/login", content=body, headers={"Origin": ORIGIN, "Content-Type": "application/json"}
    )
    assert response.status_code in (400, 401)
    assert "www-authenticate" not in response.headers


def test_unknown_mode_or_incomplete_hosted_settings_refuse_startup(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "public")
    with pytest.raises(RuntimeError, match="LAB_MODE"):
        AccessSettings.from_environment()
    monkeypatch.setenv("LAB_MODE", "hosted")
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    for origin in (
        "",
        "http://lab.example.com",
        "https://lab.example.com/path",
        "https://u:p@lab.example.com",
    ):
        monkeypatch.setenv("LAB_PUBLIC_ORIGIN", origin)
        with pytest.raises(RuntimeError, match="HTTPS"):
            AccessSettings.from_environment()
    monkeypatch.setenv("LAB_PUBLIC_ORIGIN", ORIGIN)
    monkeypatch.setenv("LAB_PASSWORD", "short")
    with pytest.raises(RuntimeError, match="password of 12"):
        AccessSettings.from_environment()
    password = secrets.token_urlsafe(9)
    monkeypatch.setenv("LAB_PASSWORD", password)
    monkeypatch.delenv("LAB_SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="LAB_SESSION_SECRET"):
        AccessSettings.from_environment()
    secret = secrets.token_urlsafe(32)
    monkeypatch.setenv("LAB_SESSION_SECRET", secret)
    settings = AccessSettings.from_environment()
    assert password not in repr(settings)
    assert secret not in repr(settings)
    assert settings.credentials_match("operator", password)


def test_local_mode_still_allows_loopback_without_credentials():
    app = FastAPI()
    app.add_middleware(AccessControls, settings=AccessSettings("local"))

    @app.post("/api/runs")
    def start():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/auth/session").json() == {"authenticated": True, "mode": "local"}
        assert client.post("/api/runs", json={}).status_code == 200
        assert (
            client.post("/api/runs", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
        )
