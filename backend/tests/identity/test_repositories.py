"""Identity repositories against real PostgreSQL (AC3.2.5, NFR2.7, NFR11.3)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.identity import repositories as repo
from app.identity.cookies import hash_secret, new_refresh_token, refresh_cookie_params
from app.identity.models import CodePurpose, OneTimeCode, RefreshSession
from app.platform.clock import FrozenClock
from tests.helpers import make_settings


def _user(session: Session, clock: FrozenClock, email: str = "Maya@Example.test") -> uuid.UUID:
    return repo.add_user(
        session, full_name="Maya", email=email.lower(), password_hash="h", now=clock.now()
    ).id


def test_find_user_by_email_is_case_insensitive(
    db_session: Session, frozen_clock: FrozenClock
) -> None:
    user_id = _user(db_session, frozen_clock)
    found = repo.find_user_by_email(db_session, "  MAYA@example.TEST ")
    assert found is not None
    assert found.id == user_id
    assert found.role == "user"
    assert found.is_verified is False
    assert repo.find_user_by_email(db_session, "nobody@example.test") is None
    assert repo.get_user(db_session, user_id) is found


def test_email_is_unique_regardless_of_case(db_session: Session, frozen_clock: FrozenClock) -> None:
    _user(db_session, frozen_clock, "dup@example.test")
    with pytest.raises(IntegrityError):
        repo.add_user(
            db_session,
            full_name="X",
            email="DUP@example.test",
            password_hash="h",
            now=frozen_clock.now(),
        )


def test_refresh_session_stores_hash_only(db_session: Session, frozen_clock: FrozenClock) -> None:
    user_id = _user(db_session, frozen_clock)
    token = new_refresh_token()
    repo.add_refresh_session(
        db_session,
        token_id=token.token_id,
        secret_hash=token.secret_hash,
        user_id=user_id,
        family_id=uuid.uuid4(),
        issued_at=frozen_clock.now(),
        expires_at=frozen_clock.now() + timedelta(days=7),
    )
    row = db_session.get(RefreshSession, token.token_id)
    assert row is not None
    assert row.secret_hash == hash_secret(token.secret)
    assert token.value.split(".", 1)[1] not in row.secret_hash
    assert token.value.startswith(f"{token.token_id}.")
    assert len(token.secret) == 32


def test_consume_code_only_once_and_supersede(
    db_session: Session, frozen_clock: FrozenClock
) -> None:
    user_id = _user(db_session, frozen_clock)
    now = frozen_clock.now()
    row = repo.add_code(
        db_session,
        user_id=user_id,
        purpose=CodePurpose.LOGIN,
        code_hash="a" * 64,
        issued_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    assert repo.live_code(db_session, user_id, CodePurpose.LOGIN) is not None
    assert repo.consume_code(db_session, row.id, now) is True
    assert repo.consume_code(db_session, row.id, now) is False
    second = repo.add_code(
        db_session,
        user_id=user_id,
        purpose=CodePurpose.LOGIN,
        code_hash="b" * 64,
        issued_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    repo.supersede_live_codes(db_session, user_id, CodePurpose.LOGIN, now)
    db_session.refresh(second)
    refreshed = db_session.get(OneTimeCode, second.id)
    assert refreshed is not None
    assert refreshed.superseded_at == now
    assert repo.live_code(db_session, user_id, CodePurpose.LOGIN) is None


def test_only_one_live_code_per_user_and_purpose(
    db_session: Session, frozen_clock: FrozenClock
) -> None:
    user_id = _user(db_session, frozen_clock)
    now = frozen_clock.now()
    kwargs = {
        "user_id": user_id,
        "purpose": CodePurpose.SIGNUP,
        "issued_at": now,
        "expires_at": now,
    }
    repo.add_code(db_session, code_hash="c" * 64, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(IntegrityError):
        repo.add_code(db_session, code_hash="d" * 64, **kwargs)  # type: ignore[arg-type]


def test_cookie_attributes_come_from_settings() -> None:
    params = refresh_cookie_params(make_settings(REFRESH_COOKIE_SAMESITE="strict"))
    assert params["key"] == "refresh_token"
    assert params["httponly"] is True
    assert params["max_age"] == 604_800
    assert params["path"] == "/auth"
    assert params["samesite"] == "strict"
    assert params["secure"] is False
