import base64
import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lab.security import AccessControls, AccessSettings


@pytest.fixture
def protected():
    password = secrets.token_urlsafe(32)
    settings = AccessSettings("hosted", "https://lab.example.com", "operator", password)
    app = FastAPI()
    app.add_middleware(AccessControls, settings=settings)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.hosts)

    @app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
    def example(path: str):
        return {"served": path}

    with TestClient(app, base_url=settings.origin) as client:
        yield client, ("operator", password)


@pytest.mark.parametrize("path", ["/", "/assets/index.js", "/api/health", "/api/runs", "/docs"])
def test_every_non_probe_route_requires_authentication(protected, path):
    client, auth = protected
    assert client.get(path).status_code == 401
    assert client.get(path, auth=("operator", "wrong")).status_code == 401
    assert client.get(path, auth=("wrong", auth[1])).status_code == 401
    assert client.get(path, auth=auth).status_code == 200
    assert (
        client.post("/api/runs", json={}, headers={"Origin": str(client.base_url).rstrip("/")}).status_code
        == 401
    )


def test_probe_does_not_grant_api_access_and_http_refuses_credentials(protected):
    client, auth = protected
    assert client.get("http://localhost/healthz").status_code == 200
    assert client.get("http://localhost/api/runs", auth=auth).status_code == 403
    assert client.get("https://untrusted.example/api/runs", auth=auth).status_code == 400


def test_authenticated_requests_still_require_same_origin_and_json(protected):
    client, auth = protected
    path = "/api/runs"
    assert client.post(path, auth=auth, json={}).status_code == 403
    assert (
        client.post(path, auth=auth, json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    )
    assert client.get(path, auth=auth, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    headers = {"Origin": "https://lab.example.com"}
    assert client.post(path, auth=auth, content="text", headers=headers).status_code == 415
    assert client.post(path, auth=auth, json={"large": "x" * 65_536}, headers=headers).status_code == 413
    response = client.post(path, auth=auth, json={}, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "max-age=" in response.headers["strict-transport-security"]


@pytest.mark.parametrize("header", ["Basic !!!", "Bearer anything", "Basic Og==", "Basic /w==", "Basic"])
def test_malformed_credentials_fail_closed(protected, header):
    client, _ = protected
    response = client.get("/", headers={"Authorization": header})
    assert response.status_code == 401
    assert "Basic" in response.headers["www-authenticate"]


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
    monkeypatch.setenv("LAB_PUBLIC_ORIGIN", "https://lab.example.com")
    monkeypatch.setenv("LAB_PASSWORD", "short")
    with pytest.raises(RuntimeError, match="random password"):
        AccessSettings.from_environment()
    password = secrets.token_urlsafe(32)
    monkeypatch.setenv("LAB_PASSWORD", password)
    settings = AccessSettings.from_environment()
    assert password not in repr(settings)
    encoded = base64.b64encode(f"operator:{password}".encode()).decode()
    assert settings.authenticated("Basic " + encoded)


def test_local_mode_still_allows_loopback_without_credentials():
    app = FastAPI()
    app.add_middleware(AccessControls, settings=AccessSettings("local"))

    @app.post("/api/runs")
    def start():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.post("/api/runs", json={}).status_code == 200
        assert (
            client.post("/api/runs", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
        )
