"""POST /auth/login and POST /auth/verify (WF-U1-2, WF-U1-3; BR2.x, BR3.x, BR4.1, BR4.2;
AC3.2.1-AC3.2.4, AC3.4.1-AC3.4.3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import RefreshSession, User
from app.identity.passwords import Argon2Params, PasswordHasher
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.platform.email.port import EmailTemplate
from tests.factories import (
    VALID_PASSWORD,
    login_code,
    make_user,
    register,
    unique_email,
    verified_user,
)


def _verify(client: TestClient, email: str, code: str, purpose: str = "signup") -> object:
    return client.post("/auth/verify", json={"email": email, "code": code, "purpose": purpose})


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


# ----------------------------------------------------------------------------- login


def test_login_emails_a_code_and_issues_no_token(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    response = client.post("/auth/login", json={"email": user.email, "password": VALID_PASSWORD})
    assert response.status_code == 202
    assert set(response.json()) == {"maskedEmail", "resendAvailableAt", "expiresAt"}
    assert "set-cookie" not in response.headers
    assert email_fake.sent[-1].template is EmailTemplate.LOGIN_CODE


@pytest.mark.parametrize("case", ["unknown", "wrong-password", "unverified"])
def test_login_failures_are_generic(
    client: TestClient,
    email_fake: RecordingEmailSender,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    dummy_calls: list[str] = []
    hasher = app.state.identity._hasher  # type: ignore[attr-defined]
    real_dummy = hasher.verify_dummy
    monkeypatch.setattr(hasher, "verify_dummy", lambda pw: dummy_calls.append(pw) or real_dummy(pw))
    if case == "unknown":
        email, password = unique_email(), VALID_PASSWORD
    elif case == "wrong-password":
        email, password = verified_user(client, email_fake).email, "Wrong2026pass"
    else:
        email, password = str(make_user(client, email_fake, verified=False)), VALID_PASSWORD
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "INVALID_CREDENTIALS"
    assert error["message"] == "Email or password is incorrect."
    assert len(dummy_calls) == (0 if case == "wrong-password" else 1)


def test_login_cooldown_and_lock(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    code = login_code(client, email_fake, user)
    again = client.post("/auth/login", json={"email": user.email, "password": VALID_PASSWORD})
    assert again.status_code == 429
    assert again.json()["error"]["code"] == "CODE_RESEND_COOLDOWN"
    for _ in range(5):
        _verify(client, user.email, _wrong(code), "login")
    frozen_clock.advance(seconds=61)
    locked = client.post("/auth/login", json={"email": user.email, "password": VALID_PASSWORD})
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "CODE_LOCKED"
    assert int(locked.headers["Retry-After"]) > 0


def test_login_rehashes_old_password_hash(
    client: TestClient, email_fake: RecordingEmailSender, db_session: Session
) -> None:
    user = verified_user(client, email_fake)
    row = db_session.scalars(select(User).where(User.email == user.email)).one()
    old_hash = PasswordHasher(Argon2Params(memory_kib=8_192, time_cost=1)).hash(VALID_PASSWORD)
    row.password_hash = old_hash
    db_session.commit()
    response = client.post("/auth/login", json={"email": user.email, "password": VALID_PASSWORD})
    assert response.status_code == 202
    db_session.refresh(row)
    assert row.password_hash != old_hash
    assert row.password_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")


# ----------------------------------------------------------------------------- verify


def test_signup_verify_signs_in_and_sets_refresh_cookie(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    db_session: Session,
) -> None:
    email = register(client)
    frozen_clock.advance(minutes=9, seconds=59)
    response = client.post(
        "/auth/verify",
        json={"email": email, "code": email_fake.last_code_for(email), "purpose": "signup"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accessToken"].count(".") == 2
    assert body["expiresAt"].startswith("2026-10-01T10:24:59")
    assert body["user"]["email"] == email
    assert body["user"]["isVerified"] is True
    assert body["user"]["role"] == "user"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("refresh_token=")
    for attribute in ("HttpOnly", "Max-Age=604800", "Path=/auth", "SameSite=lax"):
        assert attribute in cookie
    assert "refresh_token" not in body
    user = db_session.scalars(select(User).where(User.email == email)).one()
    db_session.refresh(user)
    assert user.is_verified is True
    assert user.verified_at == frozen_clock.now()
    raw_value = cookie.split(";", 1)[0].split("=", 1)[1]
    token_id, secret = raw_value.split(".", 1)
    session_row = db_session.get(RefreshSession, __import__("uuid").UUID(token_id))
    assert session_row is not None
    assert secret not in session_row.secret_hash
    assert session_row.user_id == user.id


def test_wrong_code_reports_attempts_left(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    email = register(client)
    code = email_fake.last_code_for(email)
    response = _verify(client, email, _wrong(code))
    assert response.status_code == 401  # type: ignore[attr-defined]
    error = response.json()["error"]  # type: ignore[attr-defined]
    assert error["code"] == "CODE_INVALID"
    assert error["details"] == [{"reason": "CODE_INVALID", "attemptsLeft": 4}]


def test_expired_code_at_ten_minutes(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    email = register(client)
    frozen_clock.advance(minutes=10)
    response = _verify(client, email, email_fake.last_code_for(email))
    assert response.status_code == 401  # type: ignore[attr-defined]
    assert response.json()["error"]["code"] == "CODE_EXPIRED"  # type: ignore[attr-defined]


def test_fifth_wrong_code_locks_with_retry_after(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    email = register(client)
    code = email_fake.last_code_for(email)
    for _ in range(4):
        _verify(client, email, _wrong(code))
    locked = _verify(client, email, _wrong(code))
    assert locked.status_code == 429  # type: ignore[attr-defined]
    assert locked.json()["error"]["code"] == "CODE_LOCKED"  # type: ignore[attr-defined]
    assert locked.headers["Retry-After"] == "900"  # type: ignore[attr-defined]
    during = _verify(client, email, code)
    assert during.status_code == 429  # type: ignore[attr-defined]


def test_purpose_mismatch_and_reuse_are_refused(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    email = register(client)
    code = email_fake.last_code_for(email)
    assert _verify(client, email, code, "login").status_code == 401  # type: ignore[attr-defined]
    assert _verify(client, email, code, "signup").status_code == 200  # type: ignore[attr-defined]
    reused = _verify(client, email, code, "signup")
    assert reused.status_code == 401  # type: ignore[attr-defined]
    assert reused.json()["error"]["code"] == "CODE_INVALID"  # type: ignore[attr-defined]


def test_unknown_email_gets_plain_code_invalid(client: TestClient) -> None:
    response = _verify(client, unique_email(), "123456")
    assert response.status_code == 401  # type: ignore[attr-defined]
    error = response.json()["error"]  # type: ignore[attr-defined]
    assert error["code"] == "CODE_INVALID"
    assert error["details"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"email": "a@example.test", "code": "12345", "purpose": "signup"},
        {"email": "a@example.test", "code": "abcdef", "purpose": "signup"},
        {"email": "a@example.test", "code": "123456", "purpose": "password_reset"},
    ],
)
def test_malformed_verify_requests(client: TestClient, body: dict[str, str]) -> None:
    response = client.post("/auth/verify", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_login_then_code_signs_in(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    code = login_code(client, email_fake, user, frozen_clock)
    response = _verify(client, user.email, code, "login")
    assert response.status_code == 200  # type: ignore[attr-defined]
    token = response.json()["accessToken"]  # type: ignore[attr-defined]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == user.email
