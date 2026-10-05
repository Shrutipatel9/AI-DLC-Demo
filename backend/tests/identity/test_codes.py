"""OTP (one-time code) service — written test-first (team Testing Posture, Step 10).

Acceptance criteria: AC3.2.1-AC3.2.5, AC3.1.3; rules BR2.1-BR2.7; NFR2.5, NFR2.10.
The service never commits; the caller commits (so failure counts persist even when the
HTTP layer then returns an error).
"""

from __future__ import annotations

import hmac
import secrets
import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.identity.codes import (
    CodeCooldownError,
    CodePolicy,
    CodeService,
    VerifyStatus,
    generate_code,
    hash_code,
)
from app.identity.models import CodePurpose, OneTimeCode, User, VerificationAttemptCounter
from app.platform.clock import FrozenClock

KEY = secrets.token_bytes(48)
SIGNUP = CodePurpose.SIGNUP
LOGIN = CodePurpose.LOGIN


def _add_user(session: Session, now: datetime) -> uuid.UUID:
    user = User(
        id=uuid.uuid4(),
        full_name="Maya Test",
        email=f"user-{uuid.uuid4().hex[:8]}@example.test",
        password_hash="not-a-real-hash",
        is_verified=False,
        role="user",
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    return user.id


@pytest.fixture
def service(frozen_clock: FrozenClock) -> CodeService:
    return CodeService(hmac_key=KEY, clock=frozen_clock)


@pytest.fixture
def user_id(db_session: Session, frozen_clock: FrozenClock) -> uuid.UUID:
    return _add_user(db_session, frozen_clock.now())


def _counter(session: Session, user: uuid.UUID, purpose: CodePurpose) -> VerificationAttemptCounter:
    row = session.get(VerificationAttemptCounter, (user, purpose.value))
    assert row is not None
    return row


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


# --- BR2.1: 6 random digits from a CSPRNG -------------------------------------------------


def test_generated_codes_are_six_digits_from_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_randbelow(upper: int) -> int:
        calls.append(upper)
        return 42

    monkeypatch.setattr("app.identity.codes.secrets.randbelow", fake_randbelow)
    assert generate_code() == "000042"
    assert calls == [10**6]


def test_real_codes_are_digits_only() -> None:
    codes = {generate_code() for _ in range(50)}
    assert all(len(code) == 6 and code.isdigit() for code in codes)
    assert len(codes) > 1


# --- BR2.2 / AC3.2.5: only a keyed hash, bound to user and purpose --------------------------


def test_hash_is_bound_to_user_and_purpose() -> None:
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    base = hash_code(KEY, user_a, SIGNUP, "123456")
    assert len(base) == 64
    assert base != hash_code(KEY, user_b, SIGNUP, "123456")
    assert base != hash_code(KEY, user_a, LOGIN, "123456")
    assert base != hash_code(secrets.token_bytes(48), user_a, SIGNUP, "123456")
    assert base == hash_code(KEY, user_a, SIGNUP, "123456")


def test_only_the_hash_is_stored(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    row = db_session.get(OneTimeCode, issued.code_id)
    assert row is not None
    assert row.code_hash == hash_code(KEY, user_id, SIGNUP, issued.code)
    assert issued.code not in row.code_hash
    assert row.issued_at == frozen_clock.now()
    assert row.expires_at == frozen_clock.now() + timedelta(minutes=10)
    assert issued.expires_at == row.expires_at
    assert issued.resend_available_at == frozen_clock.now() + timedelta(seconds=60)
    assert _counter(db_session, user_id, SIGNUP).last_sent_at == frozen_clock.now()


def test_comparison_is_constant_time(
    service: CodeService,
    db_session: Session,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    calls: list[tuple[str, str]] = []
    real = hmac.compare_digest

    def spy(a: str, b: str) -> bool:
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr("app.identity.codes.hmac.compare_digest", spy)
    assert service.verify(db_session, user_id, SIGNUP, issued.code).status is VerifyStatus.OK
    assert calls


# --- BR2.3 / AC3.2.1, AC3.2.2: valid before 10:00, expired at 10:00 -------------------------


def test_code_is_valid_at_nine_fifty_nine(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    frozen_clock.advance(minutes=9, seconds=59)
    result = service.verify(db_session, user_id, SIGNUP, issued.code)
    assert result.status is VerifyStatus.OK


def test_code_is_expired_at_ten_minutes_and_not_counted(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    frozen_clock.advance(minutes=10)
    result = service.verify(db_session, user_id, SIGNUP, issued.code)
    assert result.status is VerifyStatus.EXPIRED
    assert _counter(db_session, user_id, SIGNUP).failed_count == 0


# --- BR2.4 / AC3.2.3: single use -------------------------------------------------------------


def test_a_code_can_be_used_once(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    assert service.verify(db_session, user_id, SIGNUP, issued.code).status is VerifyStatus.OK
    row = db_session.get(OneTimeCode, issued.code_id)
    assert row is not None
    assert row.consumed_at == frozen_clock.now()
    again = service.verify(db_session, user_id, SIGNUP, issued.code)
    assert again.status is VerifyStatus.INVALID


# --- BR2.5 / AC3.2.4: purpose isolation ------------------------------------------------------


def test_signup_code_is_refused_for_login(
    service: CodeService, db_session: Session, user_id: uuid.UUID
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    result = service.verify(db_session, user_id, LOGIN, issued.code)
    assert result.status is VerifyStatus.INVALID
    # The signup code still works for its own purpose.
    assert service.verify(db_session, user_id, SIGNUP, issued.code).status is VerifyStatus.OK


# --- BR2.6 / AC3.1.3: 60 s cooldown that supersedes the old code -----------------------------


def test_resend_cooldown_then_new_code_supersedes_old(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    first = service.issue(db_session, user_id, SIGNUP)
    frozen_clock.advance(seconds=59)
    with pytest.raises(CodeCooldownError) as caught:
        service.issue(db_session, user_id, SIGNUP)
    assert caught.value.retry_after == 1
    frozen_clock.advance(seconds=1)
    second = service.issue(db_session, user_id, SIGNUP)
    old_row = db_session.get(OneTimeCode, first.code_id)
    assert old_row is not None
    assert old_row.superseded_at == frozen_clock.now()
    if first.code != second.code:
        assert (
            service.verify(db_session, user_id, SIGNUP, first.code).status is VerifyStatus.INVALID
        )
    assert service.verify(db_session, user_id, SIGNUP, second.code).status is VerifyStatus.OK


def test_cooldown_is_per_purpose(
    service: CodeService, db_session: Session, user_id: uuid.UUID
) -> None:
    service.issue(db_session, user_id, SIGNUP)
    service.issue(db_session, user_id, LOGIN)  # different purpose: no cooldown


def test_supersede_makes_a_code_unverifiable(
    service: CodeService, db_session: Session, user_id: uuid.UUID
) -> None:
    issued = service.issue(db_session, user_id, LOGIN)
    service.supersede(db_session, issued.code_id)
    assert service.verify(db_session, user_id, LOGIN, issued.code).status is VerifyStatus.INVALID


# --- BR2.7: 5 failures lock for 15 minutes; resend does not reset; success resets -------------


def test_fifth_failure_locks_for_fifteen_minutes(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    issued = service.issue(db_session, user_id, LOGIN)
    wrong = _wrong(issued.code)
    attempts_left = [
        service.verify(db_session, user_id, LOGIN, wrong).attempts_left for _ in range(4)
    ]
    assert attempts_left == [4, 3, 2, 1]
    fifth = service.verify(db_session, user_id, LOGIN, wrong)
    assert fifth.status is VerifyStatus.LOCKED
    assert fifth.locked_now is True
    assert fifth.retry_after == 15 * 60
    assert _counter(db_session, user_id, LOGIN).locked_until == frozen_clock.now() + timedelta(
        minutes=15
    )
    # A correct code during the lock is refused, and does not consume the code.
    frozen_clock.advance(minutes=1)
    during = service.verify(db_session, user_id, LOGIN, issued.code)
    assert during.status is VerifyStatus.LOCKED
    assert during.retry_after == 14 * 60
    assert during.locked_now is False


def test_lock_ends_at_fifteen_minutes_and_resets_the_count(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    issued = service.issue(db_session, user_id, LOGIN)
    for _ in range(5):
        service.verify(db_session, user_id, LOGIN, _wrong(issued.code))
    frozen_clock.advance(minutes=14, seconds=59)
    assert service.verify(db_session, user_id, LOGIN, issued.code).status is VerifyStatus.LOCKED
    frozen_clock.advance(seconds=1)
    fresh = service.issue(db_session, user_id, LOGIN)
    after = service.verify(db_session, user_id, LOGIN, _wrong(fresh.code))
    assert after.status is VerifyStatus.INVALID
    assert after.attempts_left == 4


def test_resend_does_not_reset_the_failure_count(
    service: CodeService, db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    first = service.issue(db_session, user_id, SIGNUP)
    for _ in range(3):
        service.verify(db_session, user_id, SIGNUP, _wrong(first.code))
    frozen_clock.advance(seconds=60)
    second = service.issue(db_session, user_id, SIGNUP)
    result = service.verify(db_session, user_id, SIGNUP, _wrong(second.code))
    assert result.attempts_left == 1


def test_success_resets_the_failure_count(
    service: CodeService, db_session: Session, user_id: uuid.UUID
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    for _ in range(2):
        service.verify(db_session, user_id, SIGNUP, _wrong(issued.code))
    assert service.verify(db_session, user_id, SIGNUP, issued.code).status is VerifyStatus.OK
    assert _counter(db_session, user_id, SIGNUP).failed_count == 0


def test_no_live_code_counts_as_a_failure(
    service: CodeService, db_session: Session, user_id: uuid.UUID
) -> None:
    result = service.verify(db_session, user_id, LOGIN, "123456")
    assert result.status is VerifyStatus.INVALID
    assert result.attempts_left == 4


def test_unknown_user_gets_plain_invalid_and_nothing_is_counted(
    service: CodeService, db_session: Session
) -> None:
    result = service.verify(db_session, None, SIGNUP, "123456")
    assert result.status is VerifyStatus.INVALID
    assert result.attempts_left is None
    assert db_session.scalars(select(VerificationAttemptCounter)).first() is None


def test_policy_values_are_configurable(
    db_session: Session, user_id: uuid.UUID, frozen_clock: FrozenClock
) -> None:
    short = CodeService(
        hmac_key=KEY,
        clock=frozen_clock,
        policy=CodePolicy(
            ttl=timedelta(minutes=1),
            cooldown=timedelta(seconds=5),
            max_failures=2,
            lock_duration=timedelta(minutes=1),
        ),
        generator=lambda: "111111",
    )
    issued = short.issue(db_session, user_id, SIGNUP)
    assert issued.code == "111111"
    assert short.verify(db_session, user_id, SIGNUP, "222222").attempts_left == 1
    assert short.verify(db_session, user_id, SIGNUP, "222222").status is VerifyStatus.LOCKED


# --- NFR2.10: atomic verification under concurrency ------------------------------------------


@pytest.fixture
def committed_user(
    committed_session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> Iterator[uuid.UUID]:
    with committed_session_factory() as session:
        user = _add_user(session, frozen_clock.now())
        session.commit()
    yield user
    with committed_session_factory() as session:
        session.execute(delete(User).where(User.id == user))
        session.commit()


def _parallel(count: int, work: Callable[[], VerifyStatus]) -> list[VerifyStatus]:
    barrier = threading.Barrier(count)
    results: list[VerifyStatus] = []
    lock = threading.Lock()

    def run() -> None:
        barrier.wait()
        status = work()
        with lock:
            results.append(status)

    threads = [threading.Thread(target=run) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    return results


def test_parallel_wrong_guesses_count_exactly_five(
    service: CodeService,
    committed_session_factory: Callable[[], Session],
    committed_user: uuid.UUID,
) -> None:
    with committed_session_factory() as session:
        issued = service.issue(session, committed_user, LOGIN)
        session.commit()

    def guess() -> VerifyStatus:
        with committed_session_factory() as session:
            result = service.verify(session, committed_user, LOGIN, _wrong(issued.code))
            session.commit()
            return result.status

    statuses = _parallel(10, guess)
    assert statuses.count(VerifyStatus.INVALID) == 4
    assert statuses.count(VerifyStatus.LOCKED) == 6
    with committed_session_factory() as session:
        assert _counter(session, committed_user, LOGIN).failed_count == 5


def test_two_parallel_correct_submissions_give_one_success(
    service: CodeService,
    committed_session_factory: Callable[[], Session],
    committed_user: uuid.UUID,
) -> None:
    with committed_session_factory() as session:
        issued = service.issue(session, committed_user, SIGNUP)
        session.commit()

    def submit() -> VerifyStatus:
        with committed_session_factory() as session:
            result = service.verify(session, committed_user, SIGNUP, issued.code)
            session.commit()
            return result.status

    statuses = _parallel(2, submit)
    assert sorted(statuses) == sorted([VerifyStatus.OK, VerifyStatus.INVALID])


def test_issue_time_is_utc_aware(
    service: CodeService, db_session: Session, user_id: uuid.UUID
) -> None:
    issued = service.issue(db_session, user_id, SIGNUP)
    assert issued.issued_at.tzinfo is not None
    assert issued.issued_at.utcoffset() == datetime(2026, 1, 1, tzinfo=UTC).utcoffset()
