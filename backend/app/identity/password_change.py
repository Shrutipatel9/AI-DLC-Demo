"""Signed-in password change (WF-U2-8; BR5.1, BR5.3; AUTH-016; US11.5).

- The current password must verify (Argon2id); a wrong one is 401 ``INVALID_CREDENTIALS``
  and changes nothing (BR5.1). The new password must meet the sign-up rule (BR4.5).
- The caller's own session is kept: the refresh cookie (``Path=/auth`` reaches this
  endpoint) is checked in constant time and must belong to the Bearer user; its **whole
  family** is kept, and every other family of the user is revoked with reason
  ``password_changed`` (U2 NFD post-review R-09, FD post-review R-03).
- With a missing or invalid cookie, the password still changes and **all** sessions are
  revoked; the client then refreshes once and, on 401, signs out with the security message.
- The password update and the revocations are one transaction (NFR5.7), and the
  revocation is lock-then-update, so it also catches a racing refresh (R-01).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import partial

import anyio.to_thread
from sqlalchemy.orm import Session

from app.identity import repositories as repo
from app.identity.models import RevokedReason
from app.identity.passwords import PasswordHasher, PasswordPolicy
from app.identity.sessions import SessionService, with_deadlock_retry
from app.platform.clock import Clock
from app.platform.errors import InvalidCredentials, NotAuthenticated, ValidationFailed
from app.platform.metrics import Metrics

logger = logging.getLogger("identity.password_change")

_policy = PasswordPolicy()


@dataclass(frozen=True)
class PasswordChanged:
    """A completed change: the family kept (if any) and how many sessions were revoked."""

    user_id: uuid.UUID
    kept_family: uuid.UUID | None
    revoked_count: int


class PasswordChangeService:
    """Changes a signed-in user's password and signs out their other sessions.

    Args:
        clock: Time source.
        hasher: Argon2id hasher.
        sessions: Session service (cookie family check and revocation).
        metrics: Optional metrics (``auth_password_changes_total``).
    """

    def __init__(
        self,
        *,
        clock: Clock,
        hasher: PasswordHasher,
        sessions: SessionService,
        metrics: Metrics | None = None,
    ) -> None:
        self._clock = clock
        self._hasher = hasher
        self._sessions = sessions
        self._metrics = metrics

    async def change(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
        cookie_value: str | None,
    ) -> PasswordChanged:
        """Change the password, keep the caller's family, revoke the rest. Commits.

        Raises:
            ValidationFailed: The new password breaks the rule (``PASSWORD_TOO_WEAK``).
            InvalidCredentials: The current password is wrong.
            NotAuthenticated: The token's user no longer exists.
        """
        if _policy.violations(new_password):
            raise ValidationFailed(
                details=[{"field": "newPassword", "reason": "PASSWORD_TOO_WEAK"}]
            )
        user = await anyio.to_thread.run_sync(repo.get_user, session, user_id)
        if user is None:
            raise NotAuthenticated()
        current_ok = await anyio.to_thread.run_sync(
            self._hasher.verify, user.password_hash, current_password
        )
        if not current_ok:
            self._count("wrong_current")
            logger.info(
                "password change refused",
                extra={"event": "auth.password.change_refused", "userId": str(user_id)},
            )
            raise InvalidCredentials("Your current password is incorrect.")
        new_hash = await anyio.to_thread.run_sync(self._hasher.hash, new_password)
        done = await anyio.to_thread.run_sync(
            partial(
                with_deadlock_retry,
                session,
                partial(self._change_tx, session, user_id, new_hash, cookie_value),
            )
        )
        self._count("changed")
        logger.info(
            "password changed",
            extra={
                "event": "auth.password.changed",
                "userId": str(user_id),
                "count": done.revoked_count,
            },
        )
        logger.info(
            "sessions revoked",
            extra={
                "event": "auth.sessions.revoked",
                "userId": str(user_id),
                "count": done.revoked_count,
                "reason": RevokedReason.PASSWORD_CHANGED.value,
            },
        )
        return done

    def _change_tx(
        self, session: Session, user_id: uuid.UUID, new_hash: str, cookie_value: str | None
    ) -> PasswordChanged:
        try:
            user = repo.get_user(session, user_id, for_update=True)
            if user is None:
                raise NotAuthenticated()
            keep = self._sessions.current_family(session, cookie_value, user_id)
            user.password_hash = new_hash
            user.updated_at = self._clock.now()
            count = self._sessions.revoke_user_sessions(
                session, user_id, RevokedReason.PASSWORD_CHANGED, keep_family=keep
            )
            session.commit()
        except BaseException:
            session.rollback()
            raise
        return PasswordChanged(user_id=user_id, kept_family=keep, revoked_count=count)

    def _count(self, outcome: str) -> None:
        if self._metrics is not None:
            self._metrics.auth_password_changes_total.labels(outcome=outcome).inc()
