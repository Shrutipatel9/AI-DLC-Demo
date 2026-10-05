"""U2 security events, log canary and metrics (NFR3.1, NFR3.2, NFR5.9, NFR5.10, NFR5.12;
NFD post-review R-07)."""

from __future__ import annotations

import base64
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.identity.models import User
from app.platform.clock import FrozenClock
from app.platform.db import create_db_engine
from app.platform.email.fake import RecordingEmailSender
from app.platform.logging import JsonFormatter
from tests.factories import unique_email, verified_user
from tests.helpers import make_settings
from tests.identity.conftest import CSRF_HEADERS, bearer, post_logout, post_refresh

NEW_PASSWORD = "Moonrise2027y"


def _attempt_id() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()


def _records(caplog: pytest.LogCaptureFixture, event: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if getattr(r, "event", None) == event]


def _full_flow(
    client: TestClient, fake: RecordingEmailSender, clock: FrozenClock
) -> dict[str, str]:
    """Run every U2 flow once and return the secrets it handled."""
    user = verified_user(client, fake)
    attempt = _attempt_id()
    first_cookie = client.cookies.get("refresh_token") or ""
    post_refresh(client, attempt)
    rotated = client.cookies.get("refresh_token") or ""
    client.cookies.set("refresh_token", first_cookie, path="/auth")
    post_refresh(client)  # replay of the rotated cookie -> reuse, family revoked
    client.cookies.set("refresh_token", rotated, path="/auth")
    post_refresh(client)  # the family is gone -> refused (REVOKED)
    client.post(
        "/auth/change-password",
        json={"currentPassword": user.password, "newPassword": NEW_PASSWORD},
        headers=bearer(user.access_token),
    )
    clock.advance(seconds=61)
    client.post("/auth/password/forgot", json={"email": user.email})
    code = fake.last_code_for(user.email)
    token = client.post(
        "/auth/password/verify-code", json={"email": user.email, "code": code}
    ).json()["resetToken"]
    client.post("/auth/password/reset", json={"resetToken": token, "newPassword": "Starlight2028z"})
    ghost = unique_email("ghost")
    for _ in range(5):
        client.post("/auth/password/verify-code", json={"email": ghost, "code": "123456"})
    post_logout(client)
    client.post("/auth/refresh", headers={"Origin": "https://evil.example"})
    app_state = client.app.state  # type: ignore[attr-defined]
    email_hash = app_state.identity._shadow.email_hash(ghost)
    return {
        "reset_token": token,
        "attempt_id": attempt,
        "email_hash": email_hash,
        "cookie": first_cookie,
        "email": user.email,
        "ghost": ghost,
        "code": code,
        "password": NEW_PASSWORD,
    }


def test_logs_never_contain_reset_tokens_attempt_ids_email_hashes_or_cookies(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    secrets_seen = _full_flow(client, email_fake, frozen_clock)
    output = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    for name, value in secrets_seen.items():
        assert value not in output, f"{name} leaked into the logs"
    assert secrets_seen["email_hash"][:8] not in output


def test_security_events_are_logged_with_allow_listed_fields(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    _full_flow(client, email_fake, frozen_clock)
    formatter = JsonFormatter()
    expected = {
        "auth.session.refreshed": logging.DEBUG,
        "auth.password.changed": logging.INFO,
        "auth.sessions.revoked": logging.INFO,
        "auth.password.reset_requested": logging.INFO,
        "auth.password.reset": logging.INFO,
        "auth.code.locked": logging.WARNING,
        "auth.session.reuse_detected": logging.WARNING,
        "auth.session.refused": logging.INFO,
        "auth.csrf.refused": logging.WARNING,
    }
    for event, level in expected.items():
        records = _records(caplog, event)
        assert records, f"missing {event}"
        assert records[0].levelno == level, event
    reuse = json.loads(formatter.format(_records(caplog, "auth.session.reuse_detected")[0]))
    assert {"familyId", "count", "userId"} <= set(reuse)
    requested = json.loads(formatter.format(_records(caplog, "auth.password.reset_requested")[0]))
    assert "•••@" in requested["email"]
    assert requested["sent"] is True
    revoked = json.loads(formatter.format(_records(caplog, "auth.sessions.revoked")[0]))
    assert revoked["reason"] == "password_changed"
    shadow_lock = json.loads(formatter.format(_records(caplog, "auth.code.locked")[-1]))
    assert shadow_lock.get("userId") in (None, "None")  # no identifier for shadow counters


def test_logout_event_names_the_family_and_count(
    client: TestClient, email_fake: RecordingEmailSender, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    verified_user(client, email_fake)
    post_logout(client)
    record = json.loads(JsonFormatter().format(_records(caplog, "auth.logout")[0]))
    assert record["count"] == 1
    assert uuid.UUID(record["familyId"])


def test_database_errors_never_put_bound_values_into_logs(engine: object) -> None:
    built = create_db_engine(make_settings())
    email = unique_email("canary")
    now = datetime.now(UTC)
    row = {
        "id": uuid.uuid4(),
        "full_name": "Canary",
        "email": email,
        "password_hash": "hash-canary-value",
        "is_verified": False,
        "role": "user",
        "created_at": now,
        "updated_at": now,
    }
    try:
        with built.connect() as conn:
            conn.execute(insert(User), [row])
            with pytest.raises(IntegrityError) as caught:
                conn.execute(insert(User), [{**row, "id": uuid.uuid4()}])
            conn.rollback()
    finally:
        built.dispose()
    # SQLAlchemy hides its parameter list (hide_parameters=True) ...
    message = str(caught.value)
    assert "hide_parameters" in message
    assert "hash-canary-value" not in message
    # ... and the JSON formatter drops PostgreSQL's DETAIL line, which echoes the key.
    record = logging.LogRecord(
        "http.errors",
        logging.ERROR,
        __file__,
        1,
        "unhandled error",
        None,
        (type(caught.value), caught.value, caught.value.__traceback__),
    )
    output = JsonFormatter().format(record)
    assert email not in output
    assert "hash-canary-value" not in output
    assert "IntegrityError (sqlstate 23505): details hidden" in output


def test_u2_metric_series_are_exposed(
    app: FastAPI,
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
) -> None:
    _full_flow(client, email_fake, frozen_clock)
    text = app.state.metrics.render().decode()
    for line in (
        'auth_refresh_total{outcome="ok"}',
        'auth_refresh_total{outcome="reuse_detected"}',
        'auth_refresh_total{outcome="csrf_refused"}',
        'auth_sessions_revoked_total{reason="reuse_detected"}',
        'auth_password_resets_total{step="requested"}',
        'auth_password_resets_total{step="code_verified"}',
        'auth_password_resets_total{step="completed"}',
        'auth_password_changes_total{outcome="changed"}',
    ):
        assert line in text, line


def test_metric_labels_never_carry_identifiers(
    app: FastAPI, client: TestClient, email_fake: RecordingEmailSender
) -> None:
    user = verified_user(client, email_fake)
    post_refresh(client)
    client.post("/auth/refresh", headers=CSRF_HEADERS)
    client.post(
        "/auth/change-password",
        json={"currentPassword": "Wrong2026pass", "newPassword": NEW_PASSWORD},
        headers=bearer(user.access_token),
    )
    text = app.state.metrics.render().decode()
    assert 'auth_password_changes_total{outcome="wrong_current"} 1.0' in text
    assert user.user_id not in text
    assert user.email not in text
