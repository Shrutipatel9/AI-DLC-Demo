"""Refresh-session service: rotation, strict reuse detection, recovery and revocation.

Rules BR2.1-BR2.4, BR2.7, BR3.1 and NFR2.1-NFR2.4, NFR2.6, NFR2.8 (U2), implemented to the
final pseudocode in the U2 NFR design post-review note (R-01, R-02):

- **Rotation.** A usable session is exchanged once: it is marked ``rotated_at`` and a child
  is created in the same family with a fresh lifetime (7 days). The cookie carries
  ``tokenId.secret``; only ``sha256(secret)`` is stored and compared in constant time.
- **Strict reuse detection.** Presenting an already-rotated session revokes the whole family
  (``reuse_detected``); there is no time-based grace window (ADR-006).
- **Lost-response recovery.** The caller sends a random per-call attempt id
  (``X-Refresh-Attempt``, 22 base64url characters). Its SHA-256 is stored on the child. A
  rotated session presented again with the same id, while its child is unused and at most
  60 s old, re-issues that child with a new secret instead of counting as reuse. A stolen
  cookie carries no attempt id, so recovery never helps a thief.
- **Locking.** The parent row is locked ``FOR UPDATE`` first, then the child, so two
  concurrent exchanges of one cookie are strictly ordered (one child). Revocations are
  lock-then-update (see :func:`app.identity.repositories.revoke_sessions`).
- **Every branch commits** before returning, and refusals are returned (not raised), so a
  family revoke is never undone by the request's rollback.

The service never sees HTTP; the route turns a :class:`Refused` into 401 ``SESSION_INVALID``
with the cookie cleared.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from psycopg.errors import DeadlockDetected
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.identity import repositories as repo
from app.identity.cookies import (
    RefreshToken,
    hash_secret,
    new_refresh_token,
    parse_refresh_cookie,
    reissue_refresh_token,
)
from app.identity.models import RefreshSession, RevokedReason
from app.identity.tokens import TokenService
from app.platform.clock import Clock
from app.platform.metrics import Metrics

logger = logging.getLogger("identity.sessions")

_ATTEMPT_ID = re.compile(r"^[A-Za-z0-9_-]{22}$")


class RefusalReason(StrEnum):
    """Why a refresh was refused (the ``SESSION_INVALID`` detail ``reason``)."""

    EXPIRED = "EXPIRED"
    INVALID = "INVALID"
    REVOKED = "REVOKED"
    REUSE_DETECTED = "REUSE_DETECTED"


@dataclass(frozen=True)
class SessionPolicy:
    """Refresh-session tunables (from settings).

    Attributes:
        ttl: Lifetime of each session from its own issue (``REFRESH_TOKEN_DAYS``).
        recovery_window: How long after a rotation the same attempt id may re-issue the
            child (``REFRESH_ATTEMPT_RECOVERY_SECONDS``).
    """

    ttl: timedelta = timedelta(days=7)
    recovery_window: timedelta = timedelta(seconds=60)


@dataclass(frozen=True)
class Refreshed:
    """A successful exchange: a new access token and the cookie to set."""

    access_token: str
    expires_at: datetime
    refresh_token: RefreshToken
    user_id: uuid.UUID
    family_id: uuid.UUID
    recovered: bool = False


@dataclass(frozen=True)
class Refused:
    """A refused exchange. ``revoked_count`` counts usable sessions this call revoked."""

    reason: RefusalReason
    user_id: uuid.UUID | None = None
    family_id: uuid.UUID | None = None
    revoked_count: int = 0


RefreshResult = Refreshed | Refused


@dataclass(frozen=True)
class LoggedOut:
    """Outcome of a logout (always a success for the caller, BR3.1)."""

    user_id: uuid.UUID | None
    family_id: uuid.UUID | None
    revoked_count: int


def is_valid_attempt_id(value: str | None) -> bool:
    """True when ``value`` is exactly 22 base64url characters (16 random bytes, NFR2.3)."""
    return value is not None and _ATTEMPT_ID.fullmatch(value) is not None


def hash_attempt_id(value: str) -> str:
    """SHA-256 of an attempt id, hex-encoded (only the hash is ever stored)."""
    return hashlib.sha256(value.encode()).hexdigest()


def _secret_matches(row: RefreshSession, token: RefreshToken) -> bool:
    return hmac.compare_digest(hash_secret(token.secret), row.secret_hash)


def _is_deadlock(exc: OperationalError) -> bool:
    return isinstance(exc.orig, DeadlockDetected)


def with_deadlock_retry[T](session: Session, work: Callable[[], T]) -> T:
    """Run one transaction; retry once if PostgreSQL broke a lock-order deadlock.

    A refresh replay locks parent then child, while a revocation locks a scope in
    ``token_id`` order, so the two can deadlock in rare races. PostgreSQL aborts one of
    them; that one is rolled back and re-run once. Any other database error propagates.
    """
    try:
        return work()
    except OperationalError as exc:
        session.rollback()
        if not _is_deadlock(exc):
            raise
        logger.warning("deadlock retried", extra={"event": "auth.session.deadlock_retried"})
        return work()


class SessionService:
    """Owns the refresh-session lifecycle.

    Args:
        clock: Time source (frozen in tests).
        tokens: Access-token service (issues the 15-minute token on refresh).
        policy: Lifetimes.
        metrics: Optional metrics (``auth_refresh_total``, ``auth_sessions_revoked_total``).
    """

    def __init__(
        self,
        *,
        clock: Clock,
        tokens: TokenService,
        policy: SessionPolicy,
        metrics: Metrics | None = None,
    ) -> None:
        self._clock = clock
        self._tokens = tokens
        self.policy = policy
        self._metrics = metrics

    # ------------------------------------------------------------------ issue

    def start(self, session: Session, user_id: uuid.UUID) -> RefreshToken:
        """Start a new family for a sign-in and return its first token. Does not commit."""
        now = self._clock.now()
        token = new_refresh_token()
        repo.add_refresh_session(
            session,
            token_id=token.token_id,
            secret_hash=token.secret_hash,
            user_id=user_id,
            family_id=uuid.uuid4(),
            issued_at=now,
            expires_at=now + self.policy.ttl,
        )
        return token

    # ------------------------------------------------------------------ refresh

    def refresh(
        self, session: Session, cookie_value: str | None, attempt_id: str | None
    ) -> RefreshResult:
        """Exchange a refresh cookie (WF-U2-5). Commits in every branch.

        Args:
            session: The request's database session.
            cookie_value: The ``refresh_token`` cookie, if any.
            attempt_id: The ``X-Refresh-Attempt`` header; malformed counts as absent.
        """
        token = parse_refresh_cookie(cookie_value)
        if token is None:
            return self._finish(Refused(RefusalReason.INVALID))
        attempt = attempt_id if is_valid_attempt_id(attempt_id) else None
        result = with_deadlock_retry(session, lambda: self._refresh_tx(session, token, attempt))
        return self._finish(result)

    def _refresh_tx(
        self, session: Session, token: RefreshToken, attempt: str | None
    ) -> RefreshResult:
        now = self._clock.now()
        parent = repo.get_refresh_session(session, token.token_id, for_update=True)
        if parent is None or not _secret_matches(parent, token):
            session.commit()
            return Refused(RefusalReason.INVALID)
        if parent.revoked_at is not None:
            session.commit()
            return Refused(RefusalReason.REVOKED, parent.user_id, parent.family_id)
        if now >= parent.expires_at:
            session.commit()
            return Refused(RefusalReason.EXPIRED, parent.user_id, parent.family_id)
        if parent.rotated_at is not None:
            return self._replayed(session, parent, attempt, now)
        return self._rotate(session, parent, attempt, now)

    def _rotate(
        self, session: Session, parent: RefreshSession, attempt: str | None, now: datetime
    ) -> RefreshResult:
        user = repo.get_user(session, parent.user_id)
        if user is None:  # defensive: sessions cascade with their user
            session.commit()
            return Refused(RefusalReason.INVALID)
        child = new_refresh_token()
        repo.add_refresh_session(
            session,
            token_id=child.token_id,
            secret_hash=child.secret_hash,
            user_id=parent.user_id,
            family_id=parent.family_id,
            parent_token_id=parent.token_id,
            issued_at=now,
            expires_at=now + self.policy.ttl,
            attempt_hash=hash_attempt_id(attempt) if attempt else None,
        )
        parent.rotated_at = now
        session.flush()
        # R-01: re-check the parent while still holding its lock; a revocation that
        # slipped in must also cover the child we just created.
        if repo.refresh_revoked_at(session, parent.token_id) is not None:
            repo.revoke_sessions(
                session, reason=RevokedReason.REUSE_DETECTED, now=now, family_id=parent.family_id
            )
            session.commit()
            return Refused(RefusalReason.REVOKED, parent.user_id, parent.family_id)
        access = self._tokens.issue_access(user.id, user.role)
        session.commit()
        return Refreshed(access.token, access.expires_at, child, user.id, parent.family_id)

    def _replayed(
        self, session: Session, parent: RefreshSession, attempt: str | None, now: datetime
    ) -> RefreshResult:
        child = repo.lock_child_session(session, parent.token_id)
        if child is not None and self._recoverable(child, attempt, now):
            user = repo.get_user(session, parent.user_id)
            if user is not None:
                reissued = reissue_refresh_token(child.token_id)
                child.secret_hash = reissued.secret_hash
                access = self._tokens.issue_access(user.id, user.role)
                session.commit()
                return Refreshed(
                    access.token,
                    access.expires_at,
                    reissued,
                    user.id,
                    parent.family_id,
                    recovered=True,
                )
        count = repo.revoke_sessions(
            session, reason=RevokedReason.REUSE_DETECTED, now=now, family_id=parent.family_id
        )
        session.commit()
        return Refused(RefusalReason.REUSE_DETECTED, parent.user_id, parent.family_id, count)

    def _recoverable(self, child: RefreshSession, attempt: str | None, now: datetime) -> bool:
        if attempt is None or child.attempt_hash is None:
            return False
        same_attempt = hmac.compare_digest(hash_attempt_id(attempt), child.attempt_hash)
        unused = child.rotated_at is None and child.revoked_at is None
        fresh = now - child.issued_at <= self.policy.recovery_window and now < child.expires_at
        return same_attempt and unused and fresh

    # ------------------------------------------------------------------ logout

    def logout(self, session: Session, cookie_value: str | None) -> LoggedOut:
        """Revoke every session of the cookie's family, even a rotated one (BR3.1, R-02).

        Succeeds (revoking nothing) when the cookie is missing, malformed or forged.
        Commits.
        """
        token = parse_refresh_cookie(cookie_value)
        if token is None:
            return LoggedOut(None, None, 0)
        outcome = with_deadlock_retry(session, lambda: self._logout_tx(session, token))
        if outcome.family_id is not None:
            self._count_revoked(RevokedReason.LOGOUT, outcome.revoked_count)
            logger.info(
                "signed out",
                extra={
                    "event": "auth.logout",
                    "userId": str(outcome.user_id),
                    "familyId": str(outcome.family_id),
                    "count": outcome.revoked_count,
                },
            )
        return outcome

    def _logout_tx(self, session: Session, token: RefreshToken) -> LoggedOut:
        row = repo.get_refresh_session(session, token.token_id)
        if row is None or not _secret_matches(row, token):
            session.commit()
            return LoggedOut(None, None, 0)
        count = repo.revoke_sessions(
            session, reason=RevokedReason.LOGOUT, now=self._clock.now(), family_id=row.family_id
        )
        session.commit()
        return LoggedOut(row.user_id, row.family_id, count)

    # ------------------------------------------------------------------ credential changes

    def current_family(
        self, session: Session, cookie_value: str | None, user_id: uuid.UUID
    ) -> uuid.UUID | None:
        """The family named by a cookie whose secret verifies and that belongs to ``user_id``.

        Used by change-password to keep the caller's own family (NFD post-review R-09).
        """
        token = parse_refresh_cookie(cookie_value)
        if token is None:
            return None
        row = repo.get_refresh_session(session, token.token_id)
        if row is None or not _secret_matches(row, token) or row.user_id != user_id:
            return None
        return row.family_id

    def revoke_user_sessions(
        self,
        session: Session,
        user_id: uuid.UUID,
        reason: RevokedReason,
        *,
        keep_family: uuid.UUID | None = None,
    ) -> int:
        """Revoke every session of the user except ``keep_family`` (lock-then-update).

        Does not commit: the caller's transaction also holds the password change.
        Returns the number of usable sessions revoked.
        """
        count = repo.revoke_sessions(
            session,
            reason=reason,
            now=self._clock.now(),
            user_id=user_id,
            exclude_family=keep_family,
        )
        self._count_revoked(reason, count)
        return count

    # ------------------------------------------------------------------ helpers

    def _finish(self, result: RefreshResult) -> RefreshResult:
        if isinstance(result, Refreshed):
            outcome = "recovered" if result.recovered else "ok"
            if result.recovered:
                logger.info(
                    "refresh recovered",
                    extra={
                        "event": "auth.session.recovered",
                        "userId": str(result.user_id),
                        "familyId": str(result.family_id),
                    },
                )
            else:
                logger.debug(
                    "session refreshed",
                    extra={
                        "event": "auth.session.refreshed",
                        "userId": str(result.user_id),
                        "familyId": str(result.family_id),
                    },
                )
        else:
            outcome = result.reason.value.lower()
            if result.reason is RefusalReason.REUSE_DETECTED:
                self._count_revoked(RevokedReason.REUSE_DETECTED, result.revoked_count)
                logger.warning(
                    "refresh token reuse detected; family revoked",
                    extra={
                        "event": "auth.session.reuse_detected",
                        "userId": str(result.user_id),
                        "familyId": str(result.family_id),
                        "count": result.revoked_count,
                    },
                )
            else:
                logger.info(
                    "refresh refused",
                    extra={"event": "auth.session.refused", "reason": result.reason.value},
                )
        if self._metrics is not None:
            self._metrics.auth_refresh_total.labels(outcome=outcome).inc()
        return result

    def _count_revoked(self, reason: RevokedReason, count: int) -> None:
        if self._metrics is not None and count:
            self._metrics.auth_sessions_revoked_total.labels(reason=reason.value).inc(count)
