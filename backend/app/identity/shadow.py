"""Shadow attempt counters for emails without a matching account (U2 FD post-review R-01).

Verify for an unknown email (``/auth/verify`` with purpose ``login`` and
``/auth/password/verify-code``) must behave exactly like a real account: ``attemptsLeft``
counts down and the fifth wrong code returns ``CODE_LOCKED`` for 15 minutes. Otherwise the
difference would reveal which emails have accounts.

The counter is keyed by ``HMAC-SHA-256(EMAIL_HASH_KEY, normalised email)``, so the email is
never stored, and it uses the same row-locked transaction shape as the account counter
(U1 plan D5). The service never commits; the caller does.
"""

from __future__ import annotations

import hashlib
import hmac

from sqlalchemy.orm import Session

from app.identity import repositories as repo
from app.identity.codes import (
    CodePolicy,
    VerifyResult,
    VerifyStatus,
    reset_expired_lock,
    seconds_until,
)
from app.identity.models import CodePurpose
from app.platform.clock import Clock
from app.platform.errors import AppError, CodeExpired, CodeInvalid, CodeLocked


def code_error(result: VerifyResult) -> AppError:
    """Map a failed :class:`VerifyResult` to its C11 error (shared by every verify path)."""
    if result.status is VerifyStatus.EXPIRED:
        return CodeExpired()
    if result.status is VerifyStatus.LOCKED:
        return CodeLocked(retry_after=result.retry_after)
    return CodeInvalid(attempts_left=result.attempts_left)


def normalise_email(email: str) -> str:
    """Trim and lower-case (the same normalisation the request schemas apply)."""
    return email.strip().lower()


class ShadowCounters:
    """Email-keyed failure counters for unknown emails.

    Args:
        key: The decoded ``EMAIL_HASH_KEY``.
        clock: Time source.
        policy: The same code policy as real accounts (5 failures, 15-minute lock).
    """

    def __init__(self, *, key: bytes, clock: Clock, policy: CodePolicy) -> None:
        self._key = key
        self._clock = clock
        self.policy = policy

    def email_hash(self, email: str) -> str:
        """Keyed hash of the normalised email (hex HMAC-SHA-256)."""
        return hmac.new(self._key, normalise_email(email).encode(), hashlib.sha256).hexdigest()

    def touch(
        self, session: Session, email_hash: str, purpose: CodePurpose, *, start_flow: bool = False
    ) -> None:
        """Upsert the counter (the same database work a real account's request does)."""
        repo.touch_email_counter(
            session, email_hash, purpose, self._clock.now(), start_flow=start_flow
        )

    def fail(self, session: Session, email_hash: str, purpose: CodePurpose) -> VerifyResult:
        """Count one wrong code for an unknown email, exactly as for a real account."""
        now = self._clock.now()
        counter = repo.lock_email_counter(session, email_hash, purpose, now)
        counter.updated_at = now
        reset_expired_lock(counter, now)
        if counter.locked_until is not None and counter.locked_until > now:
            session.flush()
            return VerifyResult(
                VerifyStatus.LOCKED, retry_after=seconds_until(counter.locked_until, now)
            )
        counter.failed_count += 1
        if counter.failed_count >= self.policy.max_failures:
            counter.locked_until = now + self.policy.lock_duration
            session.flush()
            return VerifyResult(
                VerifyStatus.LOCKED,
                retry_after=seconds_until(counter.locked_until, now),
                locked_now=True,
            )
        session.flush()
        return VerifyResult(
            VerifyStatus.INVALID, attempts_left=self.policy.max_failures - counter.failed_count
        )
