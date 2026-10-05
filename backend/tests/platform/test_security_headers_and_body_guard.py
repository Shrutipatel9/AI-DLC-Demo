"""Security headers, CORS and the auth body-size guard (NFR2.12, NFR2.13, NFR3.5, D4)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from tests.helpers import make_settings
from tests.platform.conftest import build_platform_app


def test_security_headers_on_every_response(platform_client: TestClient) -> None:
    response = platform_client.get("/items/1")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Cache-Control" not in response.headers
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    auth = platform_client.post("/auth/echo", json={"name": "ok"})
    assert auth.headers["Cache-Control"] == "no-store"


def test_no_hsts_in_development() -> None:
    app = build_platform_app(make_settings(APP_ENV="development"))
    with TestClient(app) as client:
        assert "Strict-Transport-Security" not in client.get("/items/1").headers


def test_cors_allows_only_the_frontend_origin(platform_client: TestClient) -> None:
    preflight = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type,x-requested-with",
    }
    allowed = platform_client.options(
        "/auth/echo", headers={"Origin": "http://localhost:3000", **preflight}
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    denied = platform_client.options(
        "/auth/echo", headers={"Origin": "https://evil.test", **preflight}
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
    simple = platform_client.get("/auth/locked", headers={"Origin": "http://localhost:3000"})
    exposed = simple.headers["access-control-expose-headers"]
    assert "Retry-After" in exposed
    assert "X-Request-ID" in exposed


def test_oversized_auth_body_with_content_length_is_refused(platform_client: TestClient) -> None:
    response = platform_client.post(
        "/auth/raw", content=b"x" * (16 * 1024 + 1), headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert error["details"] == [{"field": "body", "reason": "BODY_TOO_LARGE"}]


def test_streamed_auth_body_without_length_is_counted(platform_client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(20):
            yield b"y" * 1024

    response = platform_client.post("/auth/raw", content=chunks())
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["reason"] == "BODY_TOO_LARGE"
    small = platform_client.post("/auth/raw", content=b"z" * 16 * 1024)
    assert small.status_code == 200
    assert small.json() == {"size": 16 * 1024}
