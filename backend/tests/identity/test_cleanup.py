"""Identity clean-up command (NFR11.3; NFD Q1, post-review R-10)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity import cleanup
from app.identity.cleanup import CleanupReport, run_cleanup
from app.identity.models import EmailAttemptCounter, PasswordResetToken, RefreshSession, User
from app.platform.clock import FrozenClock

DAY = timedelta(days=1)


def _user(session: Session, now: datetime) -> uuid.UUID:
    user = User(
        id=uuid.uuid4(),
        full_name="Cleanup",
        email=f"clean-{uuid.uuid4().hex[:8]}@example.test",
        password_hash="x",
        is_verified=True,
        role="user",
        created_at=now,
        updated_at=now,
        verified_at=now,
    )
    session.add(user)
    session.flush()
    return user.id


def _session_row(
    session: Session,
    user_id: uuid.UUID,
    issued: datetime,
    *,
    parent: uuid.UUID | None = None,
    family: uuid.UUID | None = None,
    rotated: datetime | None = None,
    revoked: datetime | None = None,
) -> uuid.UUID:
    row = RefreshSession(
        token_id=uuid.uuid4(),
        secret_hash="0" * 64,
        user_id=user_id,
        family_id=family or uuid.uuid4(),
        parent_token_id=parent,
        issued_at=issued,
        expires_at=issued + 7 * DAY,
        rotated_at=rotated,
        revoked_at=revoked,
        revoked_reason="logout" if revoked else None,
    )
    session.add(row)
    session.flush()
    return row.token_id


def _ids(session: Session) -> set[uuid.UUID]:
    return set(
        session.scalars(
            select(RefreshSession.token_id).execution_options(populate_existing=True)
        ).all()
    )


def test_only_sessions_older_than_thirty_days_are_deleted(
    db_session: Session, session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    now = frozen_clock.now()
    user_id = _user(db_session, now)
    old_expired = _session_row(db_session, user_id, now - 40 * DAY)
    old_revoked = _session_row(db_session, user_id, now - 5 * DAY, revoked=now - 31 * DAY)
    active = _session_row(db_session, user_id, now - DAY)
    recently_expired = _session_row(db_session, user_id, now - 20 * DAY)
    recently_revoked = _session_row(db_session, user_id, now - 2 * DAY, revoked=now - DAY)
    db_session.commit()
    report = run_cleanup(session_factory, frozen_clock)
    remaining = _ids(db_session)
    assert report.refresh_sessions >= 2
    assert not {old_expired, old_revoked} & remaining
    assert {active, recently_expired, recently_revoked} <= remaining


def test_deleting_an_old_rotated_parent_keeps_its_live_child(
    db_session: Session, session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    now = frozen_clock.now()
    user_id = _user(db_session, now)
    family = uuid.uuid4()
    parent = _session_row(
        db_session, user_id, now - 40 * DAY, family=family, rotated=now - 33 * DAY
    )
    child = _session_row(db_session, user_id, now - DAY, family=family, parent=parent)
    db_session.commit()
    run_cleanup(session_factory, frozen_clock)
    survivor = db_session.get(RefreshSession, child, populate_existing=True)
    assert db_session.get(RefreshSession, parent, populate_existing=True) is None
    assert survivor is not None
    assert survivor.parent_token_id is None


def test_old_reset_tokens_and_idle_unlocked_shadow_counters_are_deleted(
    db_session: Session, session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    now = frozen_clock.now()
    user_id = _user(db_session, now)

    def token(issued: datetime, used: datetime | None) -> str:
        value = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        db_session.add(
            PasswordResetToken(
                reset_token_id=uuid.uuid4(),
                user_id=user_id,
                token_hash=value,
                issued_at=issued,
                expires_at=issued + timedelta(minutes=10),
                used_at=used,
            )
        )
        return value

    old_used = token(now - 40 * DAY, now - 40 * DAY)
    old_expired = token(now - 31 * DAY, None)
    fresh = token(now - DAY, None)

    def counter(updated: datetime, locked_until: datetime | None) -> str:
        key = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        db_session.add(
            EmailAttemptCounter(
                email_hash=key,
                purpose="login",
                failed_count=5 if locked_until else 1,
                locked_until=locked_until,
                updated_at=updated,
            )
        )
        return key

    idle = counter(now - 2 * DAY, None)
    idle_lock_ended = counter(now - 2 * DAY, now - DAY)
    still_locked = counter(now - 2 * DAY, now + timedelta(minutes=5))
    active = counter(now - timedelta(hours=1), None)
    db_session.commit()

    report = run_cleanup(session_factory, frozen_clock)
    assert report.password_reset_tokens >= 2
    hashes = set(
        db_session.scalars(
            select(PasswordResetToken.token_hash).execution_options(populate_existing=True)
        )
    )
    assert fresh in hashes
    assert not {old_used, old_expired} & hashes
    keys = set(db_session.scalars(select(EmailAttemptCounter.email_hash)))
    assert {still_locked, active} <= keys
    assert not {idle, idle_lock_ended} & keys


def test_batches_cover_everything_and_a_second_run_deletes_nothing(
    db_session: Session, session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    now = frozen_clock.now()
    user_id = _user(db_session, now)
    for _ in range(5):
        _session_row(db_session, user_id, now - 60 * DAY)
    db_session.commit()
    first = run_cleanup(session_factory, frozen_clock, batch_size=2)
    assert first.refresh_sessions >= 5
    second = run_cleanup(session_factory, frozen_clock, batch_size=2)
    assert second == CleanupReport(0, 0, 0)


def test_the_command_prints_a_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cleanup, "run_cleanup", lambda *_args, **_kwargs: CleanupReport(3, 2, 1))
    assert cleanup.main() == 0
    out = capsys.readouterr().out
    assert "Deleted 3 refresh sessions, 2 reset tokens, 1 shadow counters." in out
