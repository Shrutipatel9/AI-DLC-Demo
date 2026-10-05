"""OTP (one-time code) service (BR2.1-BR2.7, NFR2.5, NFR2.10).

- Codes are 6 digits from ``secrets.randbelow`` (BR2.1).
- Only ``HMAC-SHA256(key, "{user_id}:{purpose}:{code}")`` is stored, so a hash is bound
  to one account and purpose; comparison uses ``hmac.compare_digest`` (BR2.2).
- A code is valid while ``now < expires_at`` (exactly 10:00 is expired), once, and only
  for its purpose (BR2.3-BR2.5).
- A new code needs 60 s since the last one and supersedes it (BR2.6).
- Wrong codes are counted per (user, purpose) on a row locked ``FOR UPDATE``; the 5th
  failure locks verification for 15 minutes; a resend never resets the count; a success
  does (BR2.7). The row lock serialises parallel guesses (NFR2.10).

The service never commits. The caller commits after ``issue`` / ``verify`` returns, so
failure counts persist even when the HTTP layer then answers with an error.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy.orm import Session

from app.identity import repositories as repo
from app.identity.models import CodePurpose, EmailAttemptCounter, VerificationAttemptCounter
from app.platform.clock import Clock

CODE_DIGITS = 6
_DUMMY_USER = uuid.UUID(int=0)


def generate_code() -> str:
    """Return 6 uniformly random digits (``000000``-``999999``) from a CSPRNG."""
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def hash_code(key: bytes, user_id: uuid.UUID, purpose: CodePurpose, code: str) -> str:
    """Keyed hash of a code, bound to the user and purpose (hex SHA-256 HMAC)."""
    message = f"{user_id}:{purpose.value}:{code}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _seconds_until(moment: datetime, now: datetime) -> int:
    return max(1, math.ceil((moment - now).total_seconds()))


def seconds_until(moment: datetime, now: datetime) -> int:
    """Whole seconds from ``now`` until ``moment`` (at least 1), for ``Retry-After``."""
    return _seconds_until(moment, now)


def reset_expired_lock(
    counter: VerificationAttemptCounter | EmailAttemptCounter, now: datetime
) -> None:
    """When a lock has ended, start counting again from zero (BR1.4)."""
    if counter.locked_until is not None and counter.locked_until <= now:
        counter.failed_count = 0
        counter.locked_until = None


class VerifyStatus(StrEnum):
    """Outcome of a verification."""

    OK = "ok"
    INVALID = "invalid"
    EXPIRED = "expired"
    LOCKED = "locked"


@dataclass(frozen=True)
class CodePolicy:
    """Tunable code rules (values come from settings)."""

    ttl: timedelta = timedelta(minutes=10)
    cooldown: timedelta = timedelta(seconds=60)
    max_failures: int = 5
    lock_duration: timedelta = timedelta(minutes=15)


@dataclass(frozen=True)
class IssuedCode:
    """A freshly issued code. ``code`` is plain text: give it only to the email step."""

    code_id: uuid.UUID
    code: str = field(repr=False)
    issued_at: datetime
    expires_at: datetime
    resend_available_at: datetime


@dataclass(frozen=True)
class VerifyResult:
    """Result of :meth:`CodeService.verify`.

    Attributes:
        status: OK, INVALID, EXPIRED or LOCKED.
        attempts_left: Remaining wrong tries before the lock (INVALID for a real user).
        retry_after: Seconds until the lock ends (LOCKED).
        locked_now: True when this very attempt started the lock.
    """

    status: VerifyStatus
    attempts_left: int | None = None
    retry_after: int | None = None
    locked_now: bool = False


class CodeCooldownError(Exception):
    """A new code was asked for within the cooldown. ``retry_after`` is in seconds."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("code resend cooldown")
        self.retry_after = retry_after


class CodeLockedError(Exception):
    """Verification is locked for this user and purpose. ``retry_after`` is in seconds."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("code verification locked")
        self.retry_after = retry_after


class CodeService:
    """Issues and verifies one-time codes.

    Args:
        hmac_key: The ``CODE_HMAC_KEY`` bytes.
        clock: Time source (frozen in tests).
        policy: Lifetimes and limits.
        generator: Code generator (tests may inject a fixed one).
    """

    def __init__(
        self,
        *,
        hmac_key: bytes,
        clock: Clock,
        policy: CodePolicy | None = None,
        generator: Callable[[], str] = generate_code,
    ) -> None:
        self._key = hmac_key
        self._clock = clock
        self.policy = policy or CodePolicy()
        self._generate = generator

    # -- issue ------------------------------------------------------------------------------

    def issue(
        self,
        session: Session,
        user_id: uuid.UUID,
        purpose: CodePurpose,
        *,
        cooldown_reserved: bool = False,
    ) -> IssuedCode:
        """Issue a new code for (user, purpose), superseding any live one (WF-U1-4).

        Args:
            session: The caller's session (the caller commits).
            user_id: The account.
            purpose: What the code is for.
            cooldown_reserved: True when the caller already checked the cooldown and
                recorded ``last_sent_at`` in an earlier transaction (U2 non-revealing
                endpoints issue the code after the response, NFD post-review R-03/R-11).

        Raises:
            CodeCooldownError: Within the cooldown of the previous send.
            CodeLockedError: While verification for this purpose is locked.
        """
        now = self._clock.now()
        counter = repo.lock_counter(session, user_id, purpose)
        self._reset_expired_lock(counter, now)
        if counter.locked_until is not None and counter.locked_until > now:
            raise CodeLockedError(_seconds_until(counter.locked_until, now))
        if counter.last_sent_at is not None and not cooldown_reserved:
            available_at = counter.last_sent_at + self.policy.cooldown
            if now < available_at:
                raise CodeCooldownError(_seconds_until(available_at, now))

        repo.supersede_live_codes(session, user_id, purpose, now)
        code = self._generate()
        row = repo.add_code(
            session,
            user_id=user_id,
            purpose=purpose,
            code_hash=hash_code(self._key, user_id, purpose, code),
            issued_at=now,
            expires_at=now + self.policy.ttl,
        )
        counter.last_sent_at = now
        session.flush()
        return IssuedCode(
            code_id=row.id,
            code=code,
            issued_at=now,
            expires_at=row.expires_at,
            resend_available_at=now + self.policy.cooldown,
        )

    def dummy_hash(self, purpose: CodePurpose, code: str) -> None:
        """Spend the same HMAC work as a real check (equal work for unknown emails)."""
        hash_code(self._key, _DUMMY_USER, purpose, code)

    def supersede(self, session: Session, code_id: uuid.UUID) -> None:
        """Make a code unverifiable (used when its email could not be sent)."""
        repo.supersede_code(session, code_id, self._clock.now())
        session.flush()

    # -- verify -----------------------------------------------------------------------------

    def verify(
        self, session: Session, user_id: uuid.UUID | None, purpose: CodePurpose, code: str
    ) -> VerifyResult:
        """Check a submitted code in one locked transaction (WF-U1-2, plan decision D5).

        An unknown user (``None``) gets a plain INVALID after the same HMAC work, and
        nothing is counted. A missing live code or a wrong code counts as a failure; an
        expired code does not.
        """
        if user_id is None:
            hash_code(self._key, _DUMMY_USER, purpose, code)
            return VerifyResult(VerifyStatus.INVALID)

        now = self._clock.now()
        counter = repo.lock_counter(session, user_id, purpose)
        self._reset_expired_lock(counter, now)
        if counter.locked_until is not None and counter.locked_until > now:
            session.flush()
            return VerifyResult(
                VerifyStatus.LOCKED, retry_after=_seconds_until(counter.locked_until, now)
            )

        row = repo.live_code(session, user_id, purpose)
        if row is None:
            return self._fail(session, counter, now)
        if now >= row.expires_at:
            session.flush()
            return VerifyResult(VerifyStatus.EXPIRED)
        submitted = hash_code(self._key, user_id, purpose, code)
        if not hmac.compare_digest(submitted, row.code_hash):
            return self._fail(session, counter, now)
        if not repo.consume_code(session, row.id, now):
            return self._fail(session, counter, now)

        counter.failed_count = 0
        counter.locked_until = None
        session.flush()
        return VerifyResult(VerifyStatus.OK)

    # -- helpers ----------------------------------------------------------------------------

    @staticmethod
    def _reset_expired_lock(
        counter: VerificationAttemptCounter | EmailAttemptCounter, now: datetime
    ) -> None:
        reset_expired_lock(counter, now)

    def _fail(
        self, session: Session, counter: VerificationAttemptCounter, now: datetime
    ) -> VerifyResult:
        counter.failed_count += 1
        if counter.failed_count >= self.policy.max_failures:
            counter.locked_until = now + self.policy.lock_duration
            session.flush()
            return VerifyResult(
                VerifyStatus.LOCKED,
                retry_after=_seconds_until(counter.locked_until, now),
                locked_now=True,
            )
        session.flush()
        return VerifyResult(
            VerifyStatus.INVALID, attempts_left=self.policy.max_failures - counter.failed_count
        )
