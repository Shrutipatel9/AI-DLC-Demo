"""GET /auth/me and secure-by-default routing (WF-U1-5; BR4.3, BR4.4; AC3.8.1, AC3.8.2;
NFR2.8, NFR5.6)."""

from __future__ import annotations

import base64
import json
import logging
import secrets
import uuid
from collections.abc import Iterable, Iterator

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session
from starlette.routing import BaseRoute

from app.identity.models import User
from app.main import create_app, route_paths
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.platform.routing import (
    DEV_ONLY_ROUTES,
    FAKE_PAYMENT_ROUTES,
    OPERATIONAL_ROUTES,
    PUBLIC_ROUTES,
    RouteClassError,
    assert_public_routes,
)
from tests.factories import verified_user
from tests.helpers import make_settings
from tests.identity.conftest import bearer


def test_me_returns_the_profile(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    response = client.get("/auth/me", headers=bearer(user.access_token))
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": user.user_id,
        "fullName": "Maya Test",
        "email": user.email,
        "isVerified": True,
        "role": "user",
        "memberSince": body["memberSince"],
    }
    assert body["memberSince"].startswith("2026-10-01T10:00:00")
    assert response.headers["Cache-Control"] == "no-store"


def _b64(data: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def _bad_tokens(valid: str, app: FastAPI, clock: FrozenClock) -> dict[str, dict[str, str]]:
    head, body, sig = valid.split(".")
    claims = jwt.decode(valid, options={"verify_signature": False})
    none_token = f"{_b64({'alg': 'none', 'kid': 'k1'})}.{body}."
    keys = app.state.settings.jwt_keys()
    reset = jwt.encode(
        {**claims, "typ": "reset"}, keys["k1"], algorithm="HS256", headers={"kid": "k1"}
    )
    return {
        "missing": {},
        "garbage": {"Authorization": "Bearer not.a.token"},
        "basic-scheme": {"Authorization": f"Basic {valid}"},
        "tampered": {"Authorization": f"Bearer {head}.{body}.{sig[::-1]}"},
        "alg-none": {"Authorization": f"Bearer {none_token}"},
        "reset-token": {"Authorization": f"Bearer {reset}"},
    }


def test_me_refuses_every_bad_token(
    client: TestClient, app: FastAPI, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    for name, headers in _bad_tokens(user.access_token, app, frozen_clock).items():
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401, name
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED", name
    frozen_clock.advance(minutes=15)
    expired = client.get("/auth/me", headers=bearer(user.access_token))
    assert expired.status_code == 401


def test_deleted_user_token_is_refused(
    client: TestClient, email_fake: RecordingEmailSender, db_session: Session
) -> None:
    user = verified_user(client, email_fake)
    db_session.execute(delete(User).where(User.id == uuid.UUID(user.user_id)))
    db_session.commit()
    assert client.get("/auth/me", headers=bearer(user.access_token)).status_code == 401


def _flatten(routes: Iterable[BaseRoute]) -> Iterator[BaseRoute]:
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from _flatten(nested.routes)
        else:
            yield route


def test_every_non_public_route_requires_a_token(client: TestClient, app: FastAPI) -> None:
    """Route enumeration (NFR2.8): router minus the explicit allow-lists must all be 401."""
    # The fake payment provider's test page (U5) exists only with PAYMENT_PROVIDER=fake,
    # which settings refuse outside development and test.
    exempt = PUBLIC_ROUTES | DEV_ONLY_ROUTES | OPERATIONAL_ROUTES | FAKE_PAYMENT_ROUTES
    checked: list[str] = []
    for route in _flatten(app.routes):
        path = getattr(route, "path", "")
        if not path or path in exempt:
            continue
        for method in sorted(set(getattr(route, "methods", {"GET"})) - {"HEAD", "OPTIONS"}):
            response = client.request(method, path.replace("{", "").replace("}", ""))
            assert response.status_code == 401, f"{method} {path}"
            assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"
            checked.append(f"{method} {path}")
    assert "GET /auth/me" in checked
    assert set(route_paths(app.routes)) >= PUBLIC_ROUTES


def test_docs_only_in_development(
    client: TestClient, engine: object, session_factory: object, frozen_clock: FrozenClock
) -> None:
    for path in ("/docs", "/openapi.json"):
        assert client.get(path).status_code == 404
    dev_app = create_app(
        make_settings(APP_ENV="development", RATE_LIMIT_BACKEND="memory"),
        clock=frozen_clock,
        email_sender=RecordingEmailSender("test"),
        engine=engine,  # type: ignore[arg-type]
        session_factory=session_factory,  # type: ignore[arg-type]
    )
    with TestClient(dev_app) as dev_client:
        assert dev_client.get("/openapi.json").status_code == 200
        assert dev_client.get("/docs").status_code == 200


def test_metrics_is_404_when_disabled_and_403_outside_allow_list(
    client: TestClient, engine: object, session_factory: object, frozen_clock: FrozenClock
) -> None:
    assert client.get("/metrics").status_code == 404
    metrics_app = create_app(
        make_settings(METRICS_ENABLED="true", METRICS_ALLOW_CIDRS="127.0.0.1/32"),
        clock=frozen_clock,
        email_sender=RecordingEmailSender("test"),
        engine=engine,  # type: ignore[arg-type]
        session_factory=session_factory,  # type: ignore[arg-type]
    )
    with TestClient(metrics_app) as outside:
        assert outside.get("/metrics/").status_code == 403
    with TestClient(metrics_app, client=("127.0.0.1", 5000)) as local:
        response = local.get("/metrics/")
        assert response.status_code == 200
        assert "http_requests_total" in response.text


def test_public_route_assertion_catches_drift() -> None:
    assert_public_routes(PUBLIC_ROUTES)
    with pytest.raises(RouteClassError, match="unexpected"):
        assert_public_routes(PUBLIC_ROUTES | {"/auth/secret"})
    with pytest.raises(RouteClassError, match="missing"):
        assert_public_routes(PUBLIC_ROUTES - {"/health"})


def test_access_log_labels_included_routes_by_template(
    client: TestClient, email_fake: RecordingEmailSender, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="http.access")
    user = verified_user(client, email_fake)
    client.get("/auth/me", headers=bearer(user.access_token))
    routes = {
        r.__dict__["route"] for r in caplog.records if getattr(r, "event", None) == "http.request"
    }
    assert {"/auth/register", "/auth/verify", "/auth/me"} <= routes


def test_start_up_refuses_unsafe_signing_keys() -> None:
    short = base64.b64encode(secrets.token_bytes(16)).decode()
    with pytest.raises(ValueError, match="at least 32 bytes"):
        make_settings(JWT_SIGNING_KEYS=json.dumps({"k1": short}))
