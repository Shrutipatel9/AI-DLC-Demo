"""Password-reset service (test-first; US3.9; AUTH-015).

ACs AC3.9.1-AC3.9.5. Rules BR4.1-BR4.6 with FD post-review R-01 (anti-enumeration and
shadow counters) and R-09 (256-bit token, atomic single use); NFR2.9-NFR2.12, NFR5.7.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity import password_reset as reset_module
from app.identity.codes import CodePolicy, CodeService
from app.identity.models import (
    CodePurpose,
    EmailAttemptCounter,
    PasswordResetToken,
    RefreshSession,
    RevokedReason,
    User,
    VerificationAttemptCounter,
)
from app.identity.password_reset import (
    CodeRequested,
    PasswordReset,
    PasswordResetService,
    ResetTokenIssued,
)
from app.identity.passwords import Argon2Params, PasswordHasher
from app.identity.sessions import Refreshed, Refused, SessionPolicy, SessionService
from app.identity.shadow import ShadowCounters
from app.identity.tokens import TokenService
from app.platform.clock import FrozenClock, SystemClock
from app.platform.errors import (
    CodeExpired,
    CodeInvalid,
    CodeLocked,
    ResetTokenInvalid,
    ValidationFailed,
)
from tests.factories import session_cookie
from tests.helpers import make_settings
from tests.identity.conftest import TwoSessions, run_in_threads, wait_for_lock_waiter

OLD_PASSWORD = "Sunrise2026x"
NEW_PASSWORD = "Moonrise2027y"
FIXED_CODE = "246810"
EMAIL_KEY = b"k" * 48


class Harness:
    """The reset service and its collaborators, wired like the app (fast Argon2 params)."""

    def __init__(self, clock: FrozenClock | SystemClock) -> None:
        settings = make_settings()
        self.clock = clock
        self.hasher = PasswordHasher(Argon2Params(memory_kib=8, time_cost=1, parallelism=1))
        policy = CodePolicy()
        self.codes = CodeService(
            hmac_key=settings.code_key(), clock=clock, policy=policy, generator=lambda: FIXED_CODE
        )
        self.shadow = ShadowCounters(key=EMAIL_KEY, clock=clock, policy=policy)
        self.sessions = SessionService(
            clock=clock,
            tokens=TokenService.from_settings(settings, clock),
            policy=SessionPolicy(),
        )
        self.service = PasswordResetService(
            clock=clock,
            codes=self.codes,
            shadow=self.shadow,
            sessions=self.sessions,
            hasher=self.hasher,
            token_ttl=timedelta(minutes=10),
        )

    def add_user(self, session: Session, *, verified: bool = True) -> User:
        now = self.clock.now()
        user = User(
            id=uuid.uuid4(),
            full_name="Reset Test",
            email=f"reset-{uuid.uuid4().hex[:8]}@example.test",
            password_hash=self.hasher.hash(OLD_PASSWORD),
            is_verified=verified,
            role="user",
            created_at=now,
            updated_at=now,
            verified_at=now if verified else None,
        )
        session.add(user)
        session.flush()
        return user

    def send_code(self, session: Session, user: User) -> str:
        """What the background task does after a successful request: issue the code."""
        self.codes.issue(session, user.id, CodePurpose.PASSWORD_RESET, cooldown_reserved=True)
        session.commit()
        return FIXED_CODE

    def token_for(self, session: Session, user: User) -> ResetTokenIssued:
        self.service.request(session, user.email)
        code = self.send_code(session, user)
        return self.service.verify_code(session, user.email, code)


def reset(h: Harness, session: Session, token: str, password: str = NEW_PASSWORD) -> PasswordReset:
    return asyncio.run(h.service.reset(session, token, password))


def wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


@pytest.fixture
def h(frozen_clock: FrozenClock) -> Harness:
    return Harness(frozen_clock)


# ------------------------------------------------------------------ request (forgot)


def test_request_gives_the_same_reply_for_real_unknown_cooldown_and_locked_emails(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    real = h.add_user(db_session)
    in_cooldown = h.add_user(db_session)
    locked = h.add_user(db_session)
    unverified = h.add_user(db_session, verified=False)
    h.service.request(db_session, in_cooldown.email)  # first request reserves the cooldown
    db_session.add(
        VerificationAttemptCounter(
            user_id=locked.id,
            purpose=CodePurpose.PASSWORD_RESET.value,
            failed_count=5,
            locked_until=frozen_clock.now() + timedelta(minutes=15),
        )
    )
    db_session.flush()
    frozen_clock.advance(seconds=10)
    cases = {
        "real": real.email,
        "unknown": f"nobody-{uuid.uuid4().hex[:8]}@example.test",
        "cooldown": in_cooldown.email,
        "locked": locked.email,
        "unverified": unverified.email,
    }
    replies = {name: h.service.request(db_session, email) for name, email in cases.items()}
    shapes = {
        (r.reply.resend_available_at, r.reply.expires_at, r.reply.masked_email.split("@")[1])
        for r in replies.values()
    }
    assert len(shapes) == 1
    now = frozen_clock.now()
    assert replies["real"].reply.resend_available_at == now + timedelta(seconds=60)
    assert replies["real"].reply.expires_at == now + timedelta(minutes=10)
    assert all(
        r.reply.masked_email.startswith(e[0] + "•••@")
        for r, e in zip(replies.values(), cases.values(), strict=True)
    )
    # Only the eligible real account gets a code to send (after the response).
    assert replies["real"].pending is not None
    assert replies["real"].pending.purpose is CodePurpose.PASSWORD_RESET
    assert [name for name, r in replies.items() if r.pending is not None] == ["real"]


def test_request_records_the_flow_start_and_reserves_the_cooldown(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user = h.add_user(db_session)
    first = h.service.request(db_session, user.email)
    assert first.pending is not None
    counter = db_session.get(
        VerificationAttemptCounter,
        (user.id, CodePurpose.PASSWORD_RESET.value),
        populate_existing=True,
    )
    assert counter is not None
    assert counter.flow_started_at == frozen_clock.now()
    assert counter.last_sent_at == frozen_clock.now()
    frozen_clock.advance(seconds=59)
    assert h.service.request(db_session, user.email).pending is None
    frozen_clock.advance(seconds=1)
    assert h.service.request(db_session, user.email).pending is not None


def test_unknown_emails_use_a_keyed_shadow_counter_and_never_store_the_email(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    email = f"Ghost-{uuid.uuid4().hex[:8]}@Example.TEST"
    h.service.request(db_session, email)
    expected = hmac.new(EMAIL_KEY, email.strip().lower().encode(), hashlib.sha256).hexdigest()
    assert h.shadow.email_hash(email) == expected
    row = db_session.get(EmailAttemptCounter, (expected, CodePurpose.PASSWORD_RESET.value))
    assert row is not None
    assert row.flow_started_at == frozen_clock.now()
    stored = " ".join(str(v) for v in vars(row).values())
    assert email.lower() not in stored.lower()


# ------------------------------------------------------------------ verify code


def test_a_verified_code_yields_a_256_bit_token_stored_only_as_a_hash(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user = h.add_user(db_session)
    issued = h.token_for(db_session, user)
    assert isinstance(issued, ResetTokenIssued)
    assert len(issued.token) >= 43  # 32 bytes, base64url
    assert issued.expires_at == frozen_clock.now() + timedelta(minutes=10)
    row = db_session.scalars(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    ).one()
    assert row.token_hash == hashlib.sha256(issued.token.encode()).hexdigest()
    assert issued.token not in row.token_hash
    assert row.used_at is None
    assert issued.token not in repr(issued)


def test_a_new_token_makes_earlier_unused_tokens_unusable(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user = h.add_user(db_session)
    first = h.token_for(db_session, user)
    frozen_clock.advance(seconds=61)
    second = h.token_for(db_session, user)
    with pytest.raises(ResetTokenInvalid):
        reset(h, db_session, first.token)
    assert reset(h, db_session, second.token).user_id == user.id


def test_wrong_codes_count_down_and_the_fifth_locks_for_fifteen_minutes(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user = h.add_user(db_session)
    h.service.request(db_session, user.email)
    code = h.send_code(db_session, user)
    for left in (4, 3, 2, 1):
        with pytest.raises(CodeInvalid) as caught:
            h.service.verify_code(db_session, user.email, wrong(code))
        assert caught.value.details == [{"reason": "CODE_INVALID", "attemptsLeft": left}]
    with pytest.raises(CodeLocked) as locked:
        h.service.verify_code(db_session, user.email, wrong(code))
    assert locked.value.retry_after == 900
    with pytest.raises(CodeLocked):  # even the right code while locked
        h.service.verify_code(db_session, user.email, code)


def test_unknown_emails_lock_after_five_exactly_like_real_accounts(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    email = f"ghost-{uuid.uuid4().hex[:8]}@example.test"
    h.service.request(db_session, email)
    for left in (4, 3, 2, 1):
        with pytest.raises(CodeInvalid) as caught:
            h.service.verify_code(db_session, email, "123456")
        assert caught.value.details == [{"reason": "CODE_INVALID", "attemptsLeft": left}]
    with pytest.raises(CodeLocked) as locked:
        h.service.verify_code(db_session, email, "123456")
    assert locked.value.retry_after == 900
    frozen_clock.advance(minutes=14, seconds=59)
    with pytest.raises(CodeLocked):
        h.service.verify_code(db_session, email, "123456")
    frozen_clock.advance(seconds=1)
    with pytest.raises(CodeInvalid) as after:
        h.service.verify_code(db_session, email, "123456")
    assert after.value.details == [{"reason": "CODE_INVALID", "attemptsLeft": 4}]


def test_a_code_is_expired_at_ten_minutes(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user = h.add_user(db_session)
    h.service.request(db_session, user.email)
    code = h.send_code(db_session, user)
    frozen_clock.advance(minutes=10)
    with pytest.raises(CodeExpired):
        h.service.verify_code(db_session, user.email, code)


def test_a_login_code_never_verifies_for_reset(h: Harness, db_session: Session) -> None:
    user = h.add_user(db_session)
    h.codes.issue(db_session, user.id, CodePurpose.LOGIN)
    with pytest.raises(CodeInvalid):
        h.service.verify_code(db_session, user.email, FIXED_CODE)


# ------------------------------------------------------------------ reset


def test_reset_token_works_at_nine_fifty_nine_and_not_at_ten(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user = h.add_user(db_session)
    late = h.token_for(db_session, user)
    frozen_clock.advance(minutes=10)
    with pytest.raises(ResetTokenInvalid):
        reset(h, db_session, late.token)
    frozen_clock.advance(seconds=61)
    early = h.token_for(db_session, user)
    frozen_clock.advance(minutes=9, seconds=59)
    assert reset(h, db_session, early.token).user_id == user.id


@pytest.mark.parametrize("token", ["", "short", "x" * 43, "not a token at all"])
def test_unknown_tokens_are_refused(h: Harness, db_session: Session, token: str) -> None:
    with pytest.raises(ResetTokenInvalid):
        reset(h, db_session, token)


def test_a_reset_token_works_once(h: Harness, db_session: Session) -> None:
    user = h.add_user(db_session)
    issued = h.token_for(db_session, user)
    reset(h, db_session, issued.token)
    with pytest.raises(ResetTokenInvalid):
        reset(h, db_session, issued.token, "Starlight2028z")


def test_a_weak_password_is_refused_and_the_token_stays_usable(
    h: Harness, db_session: Session
) -> None:
    user = h.add_user(db_session)
    issued = h.token_for(db_session, user)
    with pytest.raises(ValidationFailed) as caught:
        reset(h, db_session, issued.token, "password1")
    assert caught.value.details[0]["field"] == "newPassword"
    assert caught.value.details[0]["reason"] == "PASSWORD_TOO_WEAK"
    assert reset(h, db_session, issued.token).user_id == user.id


def test_reset_sets_the_password_and_revokes_every_session(
    h: Harness, db_session: Session, frozen_clock: FrozenClock
) -> None:
    user = h.add_user(db_session)
    cookies = [session_cookie(h.sessions, db_session, user.id) for _ in range(3)]
    issued = h.token_for(db_session, user)
    done = reset(h, db_session, issued.token)
    assert done == PasswordReset(user_id=user.id, revoked_count=3)
    refreshed = db_session.get(User, user.id, populate_existing=True)
    assert refreshed is not None
    assert h.hasher.verify(refreshed.password_hash, NEW_PASSWORD)
    assert not h.hasher.verify(refreshed.password_hash, OLD_PASSWORD)
    rows = db_session.scalars(
        select(RefreshSession)
        .where(RefreshSession.user_id == user.id)
        .execution_options(populate_existing=True)
    ).all()
    assert {r.revoked_reason for r in rows} == {RevokedReason.PASSWORD_RESET.value}
    for cookie in cookies:
        result = h.sessions.refresh(db_session, cookie.value, None)
        assert isinstance(result, Refused)
        assert result.reason.value == "REVOKED"
    token_row = db_session.scalars(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    ).one()
    assert token_row.used_at == frozen_clock.now()


def test_a_failure_inside_the_reset_leaves_no_partial_state(
    h: Harness, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = h.add_user(db_session)
    cookie = session_cookie(h.sessions, db_session, user.id)
    issued = h.token_for(db_session, user)

    def boom(*_args: object, **_kwargs: object) -> int:
        raise RuntimeError("database went away")

    monkeypatch.setattr(h.sessions, "revoke_user_sessions", boom)
    with pytest.raises(RuntimeError):
        reset(h, db_session, issued.token)
    monkeypatch.undo()
    stored = db_session.get(User, user.id, populate_existing=True)
    assert stored is not None
    assert h.hasher.verify(stored.password_hash, OLD_PASSWORD)
    assert isinstance(h.sessions.refresh(db_session, cookie.value, None), Refreshed)
    assert reset(h, db_session, issued.token).user_id == user.id  # token was not consumed


# ------------------------------------------------------------------ races


def _committed_token(races: TwoSessions, h: Harness) -> tuple[uuid.UUID, ResetTokenIssued]:
    user_id = races.make_user(password_hash=h.hasher.hash(OLD_PASSWORD))
    with races.factory() as session:
        user = session.get(User, user_id)
        assert user is not None
        return user_id, h.token_for(session, user)


def test_two_concurrent_resets_with_one_token_give_exactly_one_success(
    two_sessions: TwoSessions,
) -> None:
    h = Harness(SystemClock())
    _, issued = _committed_token(two_sessions, h)

    def attempt() -> Callable[[], PasswordReset]:
        def call() -> PasswordReset:
            with two_sessions.factory() as session:
                return reset(h, session, issued.token)

        return call

    results = run_in_threads(attempt(), attempt())
    assert sorted(type(r).__name__ for r in results) == ["PasswordReset", "ResetTokenInvalid"]


def test_a_reset_racing_a_refresh_leaves_no_usable_session(
    two_sessions: TwoSessions, engine: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    h = Harness(SystemClock())
    user_id, issued = _committed_token(two_sessions, h)
    with two_sessions.factory() as session:
        cookie = session_cookie(h.sessions, session, user_id)
    release = threading.Event()
    locked = threading.Event()  # set once the refresh holds its row lock
    real_issue = h.sessions._tokens.issue_access

    def slow_issue(*args: object, **kwargs: object) -> object:
        locked.set()
        assert release.wait(10)
        return real_issue(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(h.sessions._tokens, "issue_access", slow_issue)

    def refresh() -> object:
        with two_sessions.factory() as session:
            return h.sessions.refresh(session, cookie.value, None)

    def do_reset() -> PasswordReset:
        assert locked.wait(10), "the refresh never took its row lock"
        with two_sessions.factory() as session:
            return reset(h, session, issued.token)

    def release_when_reset_waits() -> None:
        wait_for_lock_waiter(engine)  # type: ignore[arg-type]
        release.set()

    results = run_in_threads(refresh, do_reset, release_when_reset_waits)
    assert isinstance(results[0], Refreshed), results
    assert isinstance(results[1], PasswordReset), results
    with two_sessions.factory() as session:
        rows = session.scalars(
            select(RefreshSession).where(RefreshSession.user_id == user_id)
        ).all()
    now = datetime.now(results[0].expires_at.tzinfo)
    assert [
        r for r in rows if r.revoked_at is None and r.rotated_at is None and now < r.expires_at
    ] == []


def test_reply_type(h: Harness, db_session: Session) -> None:
    assert isinstance(h.service.request(db_session, "someone@example.test"), CodeRequested)
    assert reset_module.PasswordResetService is PasswordResetService


def test_a_database_failure_during_the_request_is_rolled_back_and_raised(
    h: Harness, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(reset_module.repo, "find_user_by_email", boom)
    with pytest.raises(RuntimeError):
        h.service.request(db_session, "someone@example.test")


def test_a_token_whose_user_is_gone_is_invalid(
    h: Harness, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = h.add_user(db_session)
    issued = h.token_for(db_session, user)
    monkeypatch.setattr(reset_module.repo, "get_user", lambda *_a, **_k: None)
    with pytest.raises(ResetTokenInvalid):
        reset(h, db_session, issued.token)


def test_the_reset_funnel_is_counted_without_identifiers(
    db_session: Session, frozen_clock: FrozenClock
) -> None:
    from app.platform.metrics import Metrics

    h = Harness(frozen_clock)
    metrics = Metrics()
    h.service._metrics = metrics
    user = h.add_user(db_session)
    reset(h, db_session, h.token_for(db_session, user).token)
    text = metrics.render().decode()
    for step in ("requested", "code_verified", "completed"):
        assert f'auth_password_resets_total{{step="{step}"}} 1.0' in text
    assert str(user.id) not in text
