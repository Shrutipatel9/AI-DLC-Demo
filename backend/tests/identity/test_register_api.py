"""POST /auth/register (WF-U1-1; BR1.1-BR1.7, BR2.6, BR2.8; AC3.1.1-AC3.1.5; NFR5.2)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import OneTimeCode, User
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.platform.email.port import EmailPermanentError, EmailTemplate, EmailTimeoutError
from tests.factories import COMMON_PASSWORD, VALID_PASSWORD, register, unique_email, verified_user


def _post(client: TestClient, **body: Any) -> Any:
    payload = {"fullName": "Maya Test", "email": unique_email(), "password": VALID_PASSWORD}
    payload.update(body)
    return client.post("/auth/register", json=payload)


def test_register_returns_202_with_masked_email_and_no_token(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    response = _post(client, email="  Maya.Smith@Example.TEST ")
    assert response.status_code == 202
    body = response.json()
    assert body["maskedEmail"] == "m•••@example.test"
    assert body["expiresAt"].startswith("2026-10-01T10:10:00")
    assert body["resendAvailableAt"].startswith("2026-10-01T10:01:00")
    assert "accessToken" not in body
    assert "set-cookie" not in response.headers
    sent = email_fake.sent[-1]
    assert sent.to == "maya.smith@example.test"
    assert sent.template is EmailTemplate.SIGNUP_CODE
    assert len(str(sent.variables["code"])) == 6


def test_new_user_is_unverified_with_hashed_password(
    client: TestClient, db_session: Session
) -> None:
    email = register(client)
    user = db_session.scalars(select(User).where(User.email == email)).one()
    assert user.is_verified is False
    assert user.verified_at is None
    assert user.role == "user"
    assert user.password_hash.startswith("$argon2id$")
    assert VALID_PASSWORD not in user.password_hash


def test_verified_email_cannot_sign_up_again(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    user = verified_user(client, email_fake)
    sent_before = len(email_fake.sent)
    response = _post(client, email=user.email.upper())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"
    assert len(email_fake.sent) == sent_before  # no code sent


@pytest.mark.parametrize(
    ("body", "field", "reason"),
    [
        ({"password": "Short1"}, "password", "PASSWORD_TOO_WEAK"),
        ({"password": "nodigitshere"}, "password", "PASSWORD_TOO_WEAK"),
        ({"password": COMMON_PASSWORD}, "password", "PASSWORD_TOO_WEAK"),
        ({"password": "a1" * 64 + "x"}, "password", "PASSWORD_TOO_WEAK"),
        ({"email": "not-an-email"}, "email", "INVALID_EMAIL"),
        ({"email": "a" * 250 + "@example.test"}, "email", "INVALID_EMAIL"),
        ({"fullName": "   "}, "fullName", "INVALID_NAME"),
        ({"fullName": "x" * 121}, "fullName", "INVALID_NAME"),
    ],
)
def test_invalid_input_is_refused_per_field(
    client: TestClient,
    email_fake: RecordingEmailSender,
    body: dict[str, str],
    field: str,
    reason: str,
) -> None:
    response = _post(client, **body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert {"field": field, "reason": reason} in error["details"]
    assert email_fake.sent == []
    if "password" in body:
        assert body["password"] not in response.text


def test_missing_fields_are_validation_errors(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": unique_email()})
    assert response.status_code == 422
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert {"fullName", "password"} <= fields


def test_re_sign_up_of_unverified_email_respects_cooldown_then_resends(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    db_session: Session,
) -> None:
    email = register(client, full_name="First Name")
    first_code = email_fake.last_code_for(email)
    frozen_clock.advance(seconds=30)
    early = _post(client, email=email, fullName="Second Name")
    assert early.status_code == 429
    assert early.json()["error"]["code"] == "CODE_RESEND_COOLDOWN"
    assert early.headers["Retry-After"] == "30"
    user = db_session.scalars(select(User).where(User.email == email)).one()
    db_session.refresh(user)
    assert user.full_name == "First Name"  # nothing changed during the cooldown

    frozen_clock.advance(seconds=30)
    again = _post(client, email=email, fullName="Second Name")
    assert again.status_code == 202
    db_session.refresh(user)
    assert user.full_name == "Second Name"
    second_code = email_fake.last_code_for(email)
    if first_code != second_code:
        old = client.post(
            "/auth/verify", json={"email": email, "code": first_code, "purpose": "signup"}
        )
        assert old.status_code == 401
    ok = client.post(
        "/auth/verify", json={"email": email, "code": second_code, "purpose": "signup"}
    )
    assert ok.status_code == 200


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (EmailPermanentError("rejected"), 502, "UPSTREAM_UNAVAILABLE"),
        (EmailTimeoutError("slow"), 504, "UPSTREAM_TIMEOUT"),
    ],
)
def test_email_failure_supersedes_the_code_and_resend_works(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    db_session: Session,
    error: Exception,
    status: int,
    code: str,
) -> None:
    email = unique_email()
    email_fake.fail_with = error  # type: ignore[assignment]
    response = _post(client, email=email)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    user = db_session.scalars(select(User).where(User.email == email)).one()
    codes = db_session.scalars(select(OneTimeCode).where(OneTimeCode.user_id == user.id)).all()
    for row in codes:
        db_session.refresh(row)
    assert len(codes) == 1
    assert codes[0].superseded_at is not None  # can never be verified (NFR5.2)

    email_fake.fail_with = None
    frozen_clock.advance(seconds=60)
    assert _post(client, email=email).status_code == 202


def test_hourly_email_cap_returns_503(
    client: TestClient, app: Any, email_fake: RecordingEmailSender
) -> None:
    app.state.identity._config = type(app.state.identity._config)(email_hourly_cap=1)
    assert _post(client).status_code == 202
    capped = _post(client)
    assert capped.status_code == 503
    assert capped.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert len(email_fake.sent) == 1


def test_oversized_body_is_refused(client: TestClient) -> None:
    response = _post(client, fullName="x" * (17 * 1024))
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"field": "body", "reason": "BODY_TOO_LARGE"}]
