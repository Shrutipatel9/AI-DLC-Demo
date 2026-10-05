"""CSRF on the cookie endpoints and CORS (AC3.6.2; BR2.5; NFR2.7, NFR2.17; FD post-review
R-08; NFD post-review R-06)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import RefreshSession
from app.platform.csrf import request_origin
from app.platform.email.fake import RecordingEmailSender
from app.platform.settings import normalise_origin
from tests.factories import verified_user
from tests.identity.conftest import FRONTEND, refresh_cookie

GOOD = {"X-Requested-With": "XMLHttpRequest", "Origin": FRONTEND}


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": FRONTEND},  # no X-Requested-With
        {"X-Requested-With": "fetch", "Origin": FRONTEND},  # wrong value
        {"X-Requested-With": "XMLHttpRequest"},  # no Origin and no Referer
        {"X-Requested-With": "XMLHttpRequest", "Origin": "null"},
        {"X-Requested-With": "XMLHttpRequest", "Origin": "https://evil.example"},
        {"X-Requested-With": "XMLHttpRequest", "Referer": "https://evil.example/page"},
    ],
    ids=["no-xrw", "bad-xrw", "no-origin", "null-origin", "other-origin", "other-referer"],
)
@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout"])
def test_cookie_endpoints_refuse_requests_that_fail_the_csrf_check_and_change_nothing(
    client: TestClient,
    email_fake: RecordingEmailSender,
    db_session: Session,
    headers: dict[str, str],
    path: str,
) -> None:
    verified_user(client, email_fake)
    before = refresh_cookie(client)
    response = client.post(path, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_CHECK_FAILED"
    assert "set-cookie" not in response.headers
    assert refresh_cookie(client) == before
    rows = db_session.scalars(select(RefreshSession)).all()
    assert all(r.rotated_at is None and r.revoked_at is None for r in rows)


def test_a_referer_from_the_allowed_origin_passes_when_origin_is_absent(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    verified_user(client, email_fake)
    response = client.post(
        "/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{FRONTEND}/home"},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("origin", "referer", "expected"),
    [
        ("HTTP://LocalHost:3000/", None, "http://localhost:3000"),
        ("https://app.example.com:443", None, "https://app.example.com"),
        ("http://app.example.com:80", None, "http://app.example.com"),
        (None, "https://app.example.com/a/b?c=d", "https://app.example.com"),
        ("null", "https://app.example.com/", None),
        (None, "not a url", None),
        ("ftp://files.example.com", None, None),
        (None, None, None),
    ],
)
def test_origins_are_normalised_before_comparison(
    origin: str | None, referer: str | None, expected: str | None
) -> None:
    assert request_origin(origin, referer) == expected


def test_normalise_origin_rejects_non_origins() -> None:
    for bad in ("localhost:3000", "http://", "http://host:notaport"):
        with pytest.raises(ValueError):
            normalise_origin(bad)
    assert normalise_origin("http://[::1]:3000") == "http://[::1]:3000"


# ----------------------------------------------------------------------------- CORS


def _preflight(client: TestClient, path: str, origin: str) -> Any:
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-requested-with,x-refresh-attempt",
        },
    )


@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout", "/auth/change-password"])
def test_preflight_from_the_allowed_origin_passes_with_credentials(
    client: TestClient, path: str
) -> None:
    response = _preflight(client, path, FRONTEND)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed = response.headers["access-control-allow-headers"].lower()
    for header in ("x-requested-with", "x-refresh-attempt", "authorization", "x-request-id"):
        assert header in allowed
    # PUT was added by U3 for PUT /onboarding/response/answers/{questionId} (contract C1).
    assert set(response.headers["access-control-allow-methods"].split(", ")) == {
        "GET",
        "POST",
        "PUT",
        "OPTIONS",
    }


@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout", "/auth/change-password"])
def test_preflight_from_any_other_origin_fails(client: TestClient, path: str) -> None:
    response = _preflight(client, path, "https://evil.example")
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_headers_are_on_error_responses_too(client: TestClient) -> None:
    refused = client.post("/auth/refresh", headers={"Origin": FRONTEND})
    assert refused.status_code == 403
    assert refused.headers["access-control-allow-origin"] == FRONTEND
    assert "Retry-After" in refused.headers.get("access-control-expose-headers", "")


@pytest.mark.parametrize(
    "settings_overrides",
    [{"CSRF_ALLOWED_ORIGINS": "https://app.example.com, http://localhost:3000/"}],
)
def test_the_csrf_allow_list_is_also_the_cors_allow_list(
    app: FastAPI, client: TestClient, settings_overrides: dict[str, str]
) -> None:
    assert app.state.settings.csrf_origins == ["https://app.example.com", "http://localhost:3000"]
    ok = _preflight(client, "/auth/refresh", "https://app.example.com")
    assert ok.headers["access-control-allow-origin"] == "https://app.example.com"
    refused = client.post(
        "/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://other.example.com"},
    )
    assert refused.status_code == 403
