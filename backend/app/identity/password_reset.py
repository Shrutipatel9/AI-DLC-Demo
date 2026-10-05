"""Forgotten-password service: request a code, verify it, set a new password.

Workflow WF-U2-7; rules BR4.1-BR4.6 as amended by the U2 FD post-review note (R-01, R-09)
and the NFD post-review note (R-01, R-03); NFR2.9-NFR2.12, NFR5.7.

- **Request (non-revealing).** Every branch (real, unknown, cooldown, locked, unverified)
  does the same work before the reply: one email HMAC, one counter upsert and one dummy
  code HMAC, then the identical ``CodeSent`` body. Only an eligible verified account gets
  a :class:`PendingCode`, which the route hands to a background task, so the email is
  issued and sent after the response.
- **Verify code.** The U1 OTP rules apply under purpose ``password_reset``. An unknown
  email counts on a shadow counter, so it locks after five wrong codes exactly like a real
  account. A verified code marks earlier unused reset tokens used and issues one opaque
  token: 32 random bytes, base64url, stored only as SHA-256, valid for the configured window.
- **Reset.** One transaction: atomically consume the token (conditional update with a
  row-count check), set the new Argon2id hash, and revoke every refresh session of the
  account (lock-then-update). Any failure rolls everything back.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial

import anyio.to_thread
from sqlalchemy.orm import Session

from app.identity import repositories as repo
from app.identity.codes import CodeService, VerifyStatus, reset_expired_lock
from app.identity.delivery import CodeSent, PendingCode
from app.identity.models import CodePurpose, RevokedReason, User
from app.identity.passwords import PasswordHasher, PasswordPolicy
from app.identity.sessions import SessionService, with_deadlock_retry
from app.identity.shadow import ShadowCounters, code_error, normalise_email
from app.platform.clock import Clock
from app.platform.errors import ResetTokenInvalid, ValidationFailed
from app.platform.logging import mask_email
from app.platform.metrics import Metrics

logger = logging.getLogger("identity.password_reset")

RESET_TOKEN_BYTES = 32
PURPOSE = CodePurpose.PASSWORD_RESET
_policy = PasswordPolicy()


def hash_reset_token(token: str) -> str:
    """SHA-256 of a reset token, hex-encoded (only the hash is stored)."""
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class CodeRequested:
    """The identical reply plus, only for an eligible account, the code to send later."""

    reply: CodeSent
    pending: PendingCode | None = field(repr=False)


@dataclass(frozen=True)
class ResetTokenIssued:
    """A single-use reset token. The raw value exists only in the verify-code response."""

    token: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class PasswordReset:
    """A completed reset: whose password changed and how many sessions were revoked."""

    user_id: uuid.UUID
    revoked_count: int


class PasswordResetService:
    """Forgot -> verify code -> reset (WF-U2-7).

    Args:
        clock: Time source.
        codes: The OTP service (purpose ``password_reset``).
        shadow: Shadow counters for unknown emails.
        sessions: Session service (revokes every session on reset).
        hasher: Argon2id hasher.
        token_ttl: Reset-token lifetime (``RESET_TOKEN_MINUTES``).
        metrics: Optional metrics (``auth_password_resets_total``).
    """

    def __init__(
        self,
        *,
        clock: Clock,
        codes: CodeService,
        shadow: ShadowCounters,
        sessions: SessionService,
        hasher: PasswordHasher,
        token_ttl: timedelta,
        metrics: Metrics | None = None,
    ) -> None:
        self._clock = clock
        self._codes = codes
        self._shadow = shadow
        self._sessions = sessions
        self._hasher = hasher
        self._token_ttl = token_ttl
        self._metrics = metrics

    # ------------------------------------------------------------------ request

    def request(self, session: Session, email: str) -> CodeRequested:
        """Request a reset code; the reply never depends on the account (BR4.1). Commits."""
        now = self._clock.now()
        normalised = normalise_email(email)
        email_hash = self._shadow.email_hash(normalised)
        self._codes.dummy_hash(PURPOSE, "000000")
        try:
            user = repo.find_user_by_email(session, normalised)
            if user is not None and user.is_verified:
                pending = self._reserve(session, user, now)
            else:
                self._shadow.touch(session, email_hash, PURPOSE, start_flow=True)
                pending = None
            session.commit()
        except BaseException:
            session.rollback()
            raise
        self._step("requested")
        logger.info(
            "password reset requested",
            extra={
                "event": "auth.password.reset_requested",
                "email": mask_email(normalised),
                "sent": pending is not None,
            },
        )
        reply = CodeSent(
            masked_email=mask_email(normalised) or "",
            resend_available_at=now + self._codes.policy.cooldown,
            expires_at=now + self._codes.policy.ttl,
        )
        return CodeRequested(reply, pending)

    def _reserve(self, session: Session, user: User, now: datetime) -> PendingCode | None:
        """Start the reset flow and reserve the 60 s send slot when allowed (BR1.6, R-06)."""
        counter = repo.lock_counter(session, user.id, PURPOSE)
        reset_expired_lock(counter, now)
        counter.flow_started_at = now
        locked = counter.locked_until is not None and counter.locked_until > now
        cooling = (
            counter.last_sent_at is not None
            and now < counter.last_sent_at + self._codes.policy.cooldown
        )
        if locked or cooling:
            session.flush()
            return None
        counter.last_sent_at = now
        session.flush()
        return PendingCode(user.id, user.email, user.full_name, PURPOSE)

    # ------------------------------------------------------------------ verify code

    def verify_code(self, session: Session, email: str, code: str) -> ResetTokenIssued:
        """Verify a reset code and issue a single-use reset token (BR4.2, BR4.3). Commits.

        Raises:
            CodeInvalid: Wrong code (with ``attemptsLeft``), for real and unknown emails.
            CodeExpired: The code is 10 minutes old or older.
            CodeLocked: Five failures; locked for 15 minutes.
        """
        normalised = normalise_email(email)
        try:
            user = repo.find_user_by_email(session, normalised)
            if user is not None and user.is_verified:
                result = self._codes.verify(session, user.id, PURPOSE, code)
            else:
                user = None
                self._codes.dummy_hash(PURPOSE, code)
                result = self._shadow.fail(session, self._shadow.email_hash(normalised), PURPOSE)
            if result.status is not VerifyStatus.OK or user is None:
                session.commit()  # failure counts must persist
                if result.locked_now:
                    logger.warning(
                        "code verification locked",
                        extra={
                            "event": "auth.code.locked",
                            "userId": str(user.id) if user else None,
                            "purpose": PURPOSE.value,
                        },
                    )
                raise code_error(result)
            issued = self._issue_token(session, user.id)
            session.commit()
        except BaseException:
            session.rollback()
            raise
        self._step("code_verified")
        return issued

    def _issue_token(self, session: Session, user_id: uuid.UUID) -> ResetTokenIssued:
        now = self._clock.now()
        repo.invalidate_reset_tokens(session, user_id, now)
        raw = secrets.token_urlsafe(RESET_TOKEN_BYTES)
        expires_at = now + self._token_ttl
        repo.add_reset_token(
            session,
            user_id=user_id,
            token_hash=hash_reset_token(raw),
            issued_at=now,
            expires_at=expires_at,
        )
        return ResetTokenIssued(token=raw, expires_at=expires_at)

    # ------------------------------------------------------------------ reset

    async def reset(self, session: Session, reset_token: str, new_password: str) -> PasswordReset:
        """Set a new password with a reset token and revoke every session (BR4.4-BR4.6).

        Raises:
            ValidationFailed: The new password breaks the rule (``PASSWORD_TOO_WEAK``).
            ResetTokenInvalid: The token is unknown, used or expired.
        """
        if _policy.violations(new_password):
            raise ValidationFailed(
                details=[{"field": "newPassword", "reason": "PASSWORD_TOO_WEAK"}]
            )
        new_hash = await anyio.to_thread.run_sync(self._hasher.hash, new_password)
        done = await anyio.to_thread.run_sync(
            partial(
                with_deadlock_retry,
                session,
                partial(self._reset_tx, session, reset_token, new_hash),
            )
        )
        self._step("completed")
        logger.info(
            "password reset",
            extra={
                "event": "auth.password.reset",
                "userId": str(done.user_id),
                "count": done.revoked_count,
            },
        )
        logger.info(
            "sessions revoked",
            extra={
                "event": "auth.sessions.revoked",
                "userId": str(done.user_id),
                "count": done.revoked_count,
                "reason": RevokedReason.PASSWORD_RESET.value,
            },
        )
        return done

    def _reset_tx(self, session: Session, reset_token: str, new_hash: str) -> PasswordReset:
        now = self._clock.now()
        try:
            user_id = repo.consume_reset_token(session, hash_reset_token(reset_token), now)
            if user_id is None:
                raise ResetTokenInvalid()
            user = repo.get_user(session, user_id, for_update=True)
            if user is None:  # defensive: tokens cascade with their user
                raise ResetTokenInvalid()
            user.password_hash = new_hash
            user.updated_at = now
            count = self._sessions.revoke_user_sessions(
                session, user_id, RevokedReason.PASSWORD_RESET
            )
            session.commit()
        except BaseException:
            session.rollback()
            raise
        return PasswordReset(user_id=user_id, revoked_count=count)

    def _step(self, step: str) -> None:
        if self._metrics is not None:
            self._metrics.auth_password_resets_total.labels(step=step).inc()
