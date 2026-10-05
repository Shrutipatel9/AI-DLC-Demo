"""C11 error envelope and handlers (BR6.1, NFR3.3, NFR5.9; AC1.8.2)."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.platform.errors import (
    CodeInvalid,
    EmailAlreadyRegistered,
    ErrorCode,
    UpstreamUnavailable,
    error_body,
)


def test_typed_error_uses_envelope_with_request_id(platform_client: TestClient) -> None:
    response = platform_client.get("/items/0")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"]
    assert body["error"]["details"] == []
    assert body["error"]["requestId"] == response.headers["X-Request-ID"]


def test_retry_after_header_on_rate_style_errors(platform_client: TestClient) -> None:
    response = platform_client.get("/auth/locked")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "CODE_LOCKED"
    assert response.headers["Retry-After"] == "120"


def test_framework_validation_error_maps_to_validation_failed(platform_client: TestClient) -> None:
    response = platform_client.post("/auth/echo", json={"name": "toolongname"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert error["details"][0]["field"] == "name"
    assert error["details"][0]["reason"] == "STRING_TOO_LONG"


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [("get", "/nope", 404, "NOT_FOUND"), ("delete", "/items/1", 405, "NOT_FOUND")],
)
def test_framework_http_errors_use_envelope(
    platform_client: TestClient, method: str, path: str, status: int, code: str
) -> None:
    response = getattr(platform_client, method)(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_unhandled_error_is_generic_500_and_logged_with_trace(
    platform_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger="http.errors")
    response = platform_client.get("/boom", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text
    # CORS still applies, so the browser can read the error (security design §1).
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    records = [r for r in caplog.records if getattr(r, "event", None) == "http.unhandled"]
    assert len(records) == 1
    assert records[0].exc_info is not None


def test_error_classes_carry_codes_and_details() -> None:
    invalid = CodeInvalid(attempts_left=3)
    assert invalid.status_code == 401
    assert invalid.details == [{"reason": "CODE_INVALID", "attemptsLeft": 3}]
    assert CodeInvalid().details == []
    assert EmailAlreadyRegistered().status_code == 409
    assert UpstreamUnavailable(status_code=503).status_code == 503
    body = error_body(ErrorCode.RATE_LIMITED, "slow down", request_id="rid")
    assert body == {
        "error": {"code": "RATE_LIMITED", "message": "slow down", "details": [], "requestId": "rid"}
    }
