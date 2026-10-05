"""Session service: rotation, strict reuse detection, attempt-id recovery and revocation
(test-first; US3.5, US3.6, US3.7, US3.11; AUTH-010-AUTH-012).

ACs: AC3.5.2, AC3.5.3, AC3.6.1, AC3.6.3, AC3.7.2, AC3.7.3. Rules: BR2.1-BR2.4, BR2.7,
BR3.1; NFR2.1-NFR2.4, NFR2.6, NFR2.8; NFD post-review R-01, R-02.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.identity import sessions as sessions_module
from app.identity.cookies import hash_secret
from app.identity.models import RefreshSession, RevokedReason, User
from app.identity.sessions import (
    LoggedOut,
    Refreshed,
    RefreshResult,
    RefusalReason,
    Refused,
    SessionPolicy,
    SessionService,
    hash_attempt_id,
    is_valid_attempt_id,
)
from app.identity.tokens import TokenService
from app.platform.clock import FrozenClock, SystemClock
from tests.factories import IssuedCookie, session_cookie
from tests.helpers import make_settings
from tests.identity.conftest import TwoSessions, run_in_threads, wait_for_lock_waiter

SEVEN_DAYS = timedelta(days=7)


def build_service(clock: FrozenClock | SystemClock) -> SessionService:
    settings = make_settings()
    return SessionService(
        clock=clock,
        tokens=TokenService.from_settings(settings, clock),
        policy=SessionPolicy(ttl=SEVEN_DAYS, recovery_window=timedelta(seconds=60)),
    )


def new_attempt_id() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()


def add_user(session: Session, now: datetime) -> uuid.UUID:
    user = User(
        id=uuid.uuid4(),
        full_name="Session Test",
        email=f"sess-{uuid.uuid4().hex[:8]}@example.test",
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


def family_rows(session: Session, family_id: uuid.UUID) -> list[RefreshSession]:
    return list(
        session.scalars(
            select(RefreshSession)
            .where(RefreshSession.family_id == family_id)
            .execution_options(populate_existing=True)
        )
    )


def usable(rows: list[RefreshSession], now: datetime) -> list[RefreshSession]:
    return [r for r in rows if r.revoked_at is None and r.rotated_at is None and now < r.expires_at]


def ok(result: RefreshResult) -> Refreshed:
    assert isinstance(result, Refreshed), result
    return result


def refused(result: RefreshResult, reason: RefusalReason) -> Refused:
    assert isinstance(result, Refused), result
    assert result.reason is reason
    return result


@pytest.fixture
def service(frozen_clock: FrozenClock) -> SessionService:
    return build_service(frozen_clock)


@pytest.fixture
def new_cookie(
    service: SessionService, db_session: Session, frozen_clock: FrozenClock
) -> Callable[[], IssuedCookie]:
    """Issue a session inside the test body (so a Red run fails in the test, not the fixture)."""

    def make() -> IssuedCookie:
        user_id = add_user(db_session, frozen_clock.now())
        return session_cookie(service, db_session, user_id)

    return make


# ------------------------------------------------------------------- issue and rotation


def test_start_stores_only_the_id_and_a_hash_of_the_secret(
    service: SessionService, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user_id = add_user(db_session, frozen_clock.now())
    token = service.start(db_session, user_id)
    row = db_session.get(RefreshSession, token.token_id)
    assert row is not None
    assert row.secret_hash == hash_secret(token.secret)
    assert token.value.split(".", 1)[1] not in row.secret_hash
    assert row.expires_at == frozen_clock.now() + SEVEN_DAYS
    assert row.parent_token_id is None
    assert row.attempt_hash is None


def test_refresh_rotates_into_the_same_family_with_a_new_cookie_and_access_token(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    frozen_clock: FrozenClock,
) -> None:
    cookie = new_cookie()
    frozen_clock.advance(minutes=14)
    result = ok(service.refresh(db_session, cookie.value, None))
    assert result.refresh_token.value != cookie.value
    assert result.family_id == cookie.family_id
    assert result.recovered is False
    parent = db_session.get(RefreshSession, cookie.token_id, populate_existing=True)
    child = db_session.get(RefreshSession, result.refresh_token.token_id)
    assert parent is not None
    assert child is not None
    assert parent.rotated_at == frozen_clock.now()
    assert child.parent_token_id == parent.token_id
    assert child.family_id == parent.family_id
    assert child.expires_at == frozen_clock.now() + SEVEN_DAYS  # fresh 7 days per rotation
    assert child.secret_hash == hash_secret(result.refresh_token.secret)
    # The access token is a normal 15-minute token for this user (AC3.6.3).
    claims = service._tokens.verify_access(result.access_token)
    assert claims.user_id == result.user_id
    assert result.expires_at == frozen_clock.now().replace(microsecond=0) + timedelta(minutes=15)


def test_second_exchange_of_a_rotated_session_revokes_the_whole_family(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    frozen_clock: FrozenClock,
) -> None:
    cookie = new_cookie()
    first = ok(service.refresh(db_session, cookie.value, None))
    frozen_clock.advance(seconds=5)
    replay = refused(service.refresh(db_session, cookie.value, None), RefusalReason.REUSE_DETECTED)
    assert replay.family_id == cookie.family_id
    assert replay.revoked_count == 1  # the live child
    rows = family_rows(db_session, cookie.family_id)
    assert all(r.revoked_at is not None for r in rows)
    assert {r.revoked_reason for r in rows} == {RevokedReason.REUSE_DETECTED.value}
    # The legitimate holder of the child is now signed out too.
    refused(service.refresh(db_session, first.refresh_token.value, None), RefusalReason.REVOKED)


def test_a_session_works_until_seven_days_and_is_expired_at_seven_days(
    service: SessionService, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user_id = add_user(db_session, frozen_clock.now())
    early = session_cookie(service, db_session, user_id)
    late = session_cookie(service, db_session, user_id)
    frozen_clock.advance(SEVEN_DAYS - timedelta(seconds=1))
    ok(service.refresh(db_session, early.value, None))
    frozen_clock.advance(seconds=1)
    result = refused(service.refresh(db_session, late.value, None), RefusalReason.EXPIRED)
    assert result.revoked_count == 0


@pytest.mark.parametrize(
    "make_value",
    [
        lambda c: None,
        lambda c: "",
        lambda c: "not-a-cookie",
        lambda c: f"{c.token_id}",
        lambda c: f"not-a-uuid.{c.value.split('.', 1)[1]}",
        lambda c: f"{c.token_id}.!!!not-base64!!!",
        lambda c: f"{uuid.uuid4()}.{c.value.split('.', 1)[1]}",
        lambda c: f"{c.token_id}.{base64.urlsafe_b64encode(b'x' * 32).rstrip(b'=').decode()}",
    ],
    ids=["missing", "empty", "no-dot", "no-secret", "bad-id", "bad-secret", "unknown", "wrong"],
)
def test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    make_value: Callable[[IssuedCookie], str | None],
) -> None:
    cookie = new_cookie()
    refused(service.refresh(db_session, make_value(cookie), None), RefusalReason.INVALID)
    row = db_session.get(RefreshSession, cookie.token_id, populate_existing=True)
    assert row is not None
    assert row.rotated_at is None
    assert row.revoked_at is None


def test_secret_comparison_is_constant_time(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cookie = new_cookie()
    calls: list[tuple[str, str]] = []
    real = sessions_module.hmac.compare_digest

    def spy(a: str, b: str) -> bool:
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(sessions_module.hmac, "compare_digest", spy)
    ok(service.refresh(db_session, cookie.value, None))
    assert calls, "the secret hash must be compared with hmac.compare_digest"


def test_a_revoked_session_is_refused_as_revoked(
    service: SessionService, db_session: Session, new_cookie: Callable[[], IssuedCookie]
) -> None:
    cookie = new_cookie()
    service.logout(db_session, cookie.value)
    refused(service.refresh(db_session, cookie.value, None), RefusalReason.REVOKED)


# ------------------------------------------------------------------- attempt-id recovery


def test_attempt_ids_must_be_22_base64url_characters_and_are_stored_hashed(
    service: SessionService, db_session: Session, new_cookie: Callable[[], IssuedCookie]
) -> None:
    cookie = new_cookie()
    attempt = new_attempt_id()
    assert is_valid_attempt_id(attempt)
    for bad in (None, "", attempt[:21], attempt + "A", "+" * 22, "/" * 22, "=" * 22):
        assert not is_valid_attempt_id(bad)
    result = ok(service.refresh(db_session, cookie.value, attempt))
    child = db_session.get(RefreshSession, result.refresh_token.token_id)
    assert child is not None
    assert child.attempt_hash == hashlib.sha256(attempt.encode()).hexdigest()
    assert child.attempt_hash == hash_attempt_id(attempt)
    assert attempt not in (child.attempt_hash or "")


def test_lost_response_is_recovered_with_the_same_attempt_id(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    frozen_clock: FrozenClock,
) -> None:
    cookie = new_cookie()
    attempt = new_attempt_id()
    lost = ok(service.refresh(db_session, cookie.value, attempt))  # response "lost"
    frozen_clock.advance(seconds=60)
    retry = ok(service.refresh(db_session, cookie.value, attempt))
    assert retry.recovered is True
    assert retry.refresh_token.token_id == lost.refresh_token.token_id
    assert retry.refresh_token.value != lost.refresh_token.value
    rows = family_rows(db_session, cookie.family_id)
    assert len(rows) == 2
    assert all(r.revoked_at is None for r in rows)
    # The re-issued secret is the only one that works now; the lost one is invalid.
    refused(service.refresh(db_session, lost.refresh_token.value, None), RefusalReason.INVALID)
    ok(service.refresh(db_session, retry.refresh_token.value, None))


@pytest.mark.parametrize("case", ["different-id", "no-id", "malformed-id", "after-60s", "used"])
def test_any_other_replay_of_a_rotated_session_is_reuse(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    frozen_clock: FrozenClock,
    case: str,
) -> None:
    cookie = new_cookie()
    attempt = new_attempt_id()
    child = ok(service.refresh(db_session, cookie.value, attempt))
    replay_id: str | None = attempt
    if case == "different-id":
        replay_id = new_attempt_id()
    elif case == "no-id":
        replay_id = None
    elif case == "malformed-id":
        replay_id = attempt[:21] + "*"
    elif case == "after-60s":
        frozen_clock.advance(seconds=61)
    else:
        ok(service.refresh(db_session, child.refresh_token.value, None))
    result = refused(
        service.refresh(db_session, cookie.value, replay_id), RefusalReason.REUSE_DETECTED
    )
    assert result.revoked_count >= 1
    assert usable(family_rows(db_session, cookie.family_id), frozen_clock.now()) == []


def test_a_child_created_without_an_attempt_id_is_never_recoverable(
    service: SessionService, db_session: Session, new_cookie: Callable[[], IssuedCookie]
) -> None:
    cookie = new_cookie()
    ok(service.refresh(db_session, cookie.value, None))
    refused(
        service.refresh(db_session, cookie.value, new_attempt_id()), RefusalReason.REUSE_DETECTED
    )


# ------------------------------------------------------------------------------- logout


def test_logout_with_a_rotated_cookie_revokes_the_live_child(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    frozen_clock: FrozenClock,
) -> None:
    cookie = new_cookie()
    first = ok(service.refresh(db_session, cookie.value, None))
    second = ok(service.refresh(db_session, first.refresh_token.value, None))
    outcome = service.logout(db_session, cookie.value)  # the oldest, rotated cookie
    assert isinstance(outcome, LoggedOut)
    assert outcome.family_id == cookie.family_id
    assert outcome.revoked_count == 1
    rows = family_rows(db_session, cookie.family_id)
    assert all(r.revoked_reason == RevokedReason.LOGOUT.value for r in rows)
    refused(service.refresh(db_session, second.refresh_token.value, None), RefusalReason.REVOKED)


@pytest.mark.parametrize("value", [None, "", "garbage", f"{uuid.uuid4()}.AAAA"])
def test_logout_without_a_usable_cookie_still_succeeds(
    service: SessionService, db_session: Session, value: str | None
) -> None:
    outcome = service.logout(db_session, value)
    assert outcome == LoggedOut(user_id=None, family_id=None, revoked_count=0)


def test_logout_with_a_wrong_secret_revokes_nothing(
    service: SessionService, db_session: Session, new_cookie: Callable[[], IssuedCookie]
) -> None:
    cookie = new_cookie()
    forged = f"{cookie.token_id}.{base64.urlsafe_b64encode(b'y' * 32).rstrip(b'=').decode()}"
    assert service.logout(db_session, forged).revoked_count == 0
    ok(service.refresh(db_session, cookie.value, None))


# ------------------------------------------------------------- current family, user revoke


def test_current_family_needs_the_right_secret_and_the_same_user(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    frozen_clock: FrozenClock,
) -> None:
    cookie = new_cookie()
    owner = db_session.get(RefreshSession, cookie.token_id)
    assert owner is not None
    assert service.current_family(db_session, cookie.value, owner.user_id) == cookie.family_id
    other_user = add_user(db_session, frozen_clock.now())
    assert service.current_family(db_session, cookie.value, other_user) is None
    assert service.current_family(db_session, None, owner.user_id) is None
    forged = f"{cookie.token_id}.{base64.urlsafe_b64encode(b'z' * 32).rstrip(b'=').decode()}"
    assert service.current_family(db_session, forged, owner.user_id) is None


def test_revoke_user_sessions_keeps_only_the_named_family(
    service: SessionService, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user_id = add_user(db_session, frozen_clock.now())
    keep, other_a, other_b = (session_cookie(service, db_session, user_id) for _ in range(3))
    reason = RevokedReason.PASSWORD_CHANGED
    kept = keep.family_id
    count = service.revoke_user_sessions(db_session, user_id, reason, keep_family=kept)
    assert count == 2
    ok(service.refresh(db_session, keep.value, None))
    for revoked in (other_a, other_b):
        refused(service.refresh(db_session, revoked.value, None), RefusalReason.REVOKED)
    assert service.revoke_user_sessions(db_session, user_id, RevokedReason.PASSWORD_RESET) == 1


# ---------------------------------------------------------------------- concurrency (R-01)


def _committed_cookie(
    races: TwoSessions, service: SessionService
) -> tuple[IssuedCookie, uuid.UUID]:
    user_id = races.make_user()
    with races.factory() as session:
        return session_cookie(service, session, user_id), user_id


def _refresh_in_own_session(
    races: TwoSessions, service: SessionService, value: str, attempt: str | None
) -> Callable[[], RefreshResult]:
    def call() -> RefreshResult:
        with races.factory() as session:
            return service.refresh(session, value, attempt)

    return call


def _usable_count(races: TwoSessions, user_id: uuid.UUID) -> int:
    with races.factory() as session:
        rows = session.scalars(select(RefreshSession).where(RefreshSession.user_id == user_id))
        return len(usable(list(rows), datetime.now(UTC)))


def test_two_parallel_refreshes_of_one_cookie_give_one_child_and_one_reuse(
    two_sessions: TwoSessions,
) -> None:
    service = build_service(SystemClock())
    cookie, user_id = _committed_cookie(two_sessions, service)
    results = run_in_threads(
        _refresh_in_own_session(two_sessions, service, cookie.value, None),
        _refresh_in_own_session(two_sessions, service, cookie.value, None),
    )
    assert sorted(type(r).__name__ for r in results) == ["Refreshed", "Refused"]
    assert [r.reason for r in results if isinstance(r, Refused)] == [RefusalReason.REUSE_DETECTED]
    with two_sessions.factory() as session:
        children = session.scalars(
            select(RefreshSession).where(RefreshSession.parent_token_id == cookie.token_id)
        ).all()
    assert len(children) == 1
    assert _usable_count(two_sessions, user_id) == 0


def test_two_parallel_refreshes_with_the_same_attempt_id_give_one_child_and_one_reissue(
    two_sessions: TwoSessions,
) -> None:
    service = build_service(SystemClock())
    cookie, user_id = _committed_cookie(two_sessions, service)
    attempt = new_attempt_id()
    results = run_in_threads(
        _refresh_in_own_session(two_sessions, service, cookie.value, attempt),
        _refresh_in_own_session(two_sessions, service, cookie.value, attempt),
    )
    assert all(isinstance(r, Refreshed) for r in results), results
    assert sorted(r.recovered for r in results) == [False, True]
    assert len({r.refresh_token.token_id for r in results}) == 1
    assert _usable_count(two_sessions, user_id) == 1


def test_logout_racing_a_refresh_leaves_no_usable_session(
    two_sessions: TwoSessions, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = build_service(SystemClock())
    cookie, user_id = _committed_cookie(two_sessions, service)
    # Hold the refresh transaction open after it has inserted the child (row lock held).
    import threading

    release = threading.Event()
    locked = threading.Event()  # set once the refresh holds its row lock
    real_issue = service._tokens.issue_access

    def slow_issue(*args: object, **kwargs: object) -> object:
        locked.set()
        assert release.wait(10)
        return real_issue(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(service._tokens, "issue_access", slow_issue)

    def logout() -> LoggedOut:
        assert locked.wait(10), "the refresh never took its row lock"
        with two_sessions.factory() as session:
            return service.logout(session, cookie.value)

    def release_when_logout_waits() -> None:
        wait_for_lock_waiter(engine)
        release.set()

    results = run_in_threads(
        _refresh_in_own_session(two_sessions, service, cookie.value, None),
        logout,
        release_when_logout_waits,
    )
    assert isinstance(results[0], Refreshed), results
    assert isinstance(results[1], LoggedOut)
    assert results[1].revoked_count >= 1
    assert _usable_count(two_sessions, user_id) == 0


# ------------------------------------------------------------------ defensive branches


def test_a_revocation_seen_on_the_re_check_also_revokes_the_new_child(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    monkeypatch: pytest.MonkeyPatch,
    frozen_clock: FrozenClock,
) -> None:
    cookie = new_cookie()
    monkeypatch.setattr(
        sessions_module.repo, "refresh_revoked_at", lambda *_args: frozen_clock.now()
    )
    refused(service.refresh(db_session, cookie.value, None), RefusalReason.REVOKED)
    assert usable(family_rows(db_session, cookie.family_id), frozen_clock.now()) == []


def test_a_session_whose_user_is_gone_is_invalid(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cookie = new_cookie()
    monkeypatch.setattr(sessions_module.repo, "get_user", lambda *_args: None)
    refused(service.refresh(db_session, cookie.value, None), RefusalReason.INVALID)


def test_a_deadlock_is_rolled_back_and_retried_once_other_errors_propagate(
    service: SessionService,
    db_session: Session,
    new_cookie: Callable[[], IssuedCookie],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from psycopg.errors import DeadlockDetected
    from sqlalchemy.exc import OperationalError

    cookie = new_cookie()
    real = sessions_module.repo.get_refresh_session
    calls = {"n": 0}

    def flaky(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("SELECT", {}, DeadlockDetected("deadlock detected"))
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(sessions_module.repo, "get_refresh_session", flaky)
    ok(service.refresh(db_session, cookie.value, None))
    assert calls["n"] == 2

    def broken(*_args: object, **_kwargs: object) -> object:
        raise OperationalError("SELECT", {}, RuntimeError("connection lost"))

    monkeypatch.setattr(sessions_module.repo, "get_refresh_session", broken)
    with pytest.raises(OperationalError):
        service.logout(db_session, cookie.value)


def test_outcomes_are_counted_without_identifiers(
    db_session: Session, frozen_clock: FrozenClock
) -> None:
    from app.platform.metrics import Metrics

    metrics = Metrics()
    settings = make_settings()
    service = SessionService(
        clock=frozen_clock,
        tokens=TokenService.from_settings(settings, frozen_clock),
        policy=SessionPolicy(),
        metrics=metrics,
    )
    user_id = add_user(db_session, frozen_clock.now())
    cookie = session_cookie(service, db_session, user_id)
    ok(service.refresh(db_session, cookie.value, None))
    refused(service.refresh(db_session, cookie.value, None), RefusalReason.REUSE_DETECTED)
    refused(service.refresh(db_session, "garbage", None), RefusalReason.INVALID)
    text = metrics.render().decode()
    assert 'auth_refresh_total{outcome="ok"} 1.0' in text
    assert 'auth_refresh_total{outcome="reuse_detected"} 1.0' in text
    assert 'auth_refresh_total{outcome="invalid"} 1.0' in text
    assert 'auth_sessions_revoked_total{reason="reuse_detected"} 1.0' in text
    assert str(user_id) not in text
    assert str(cookie.family_id) not in text
