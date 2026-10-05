"""Code delivery: the ``CodeSent`` reply and sending codes after the response.

Two delivery paths exist:

- **Visible endpoints** (sign-up, login, signup resend) keep U1's synchronous
  commit -> send -> compensate in :class:`app.identity.services.IdentityService`.
- **Non-revealing endpoints** (forgot password; resend for ``login`` and
  ``password_reset``) answer 202 first and then run :meth:`CodeDelivery.deliver` as a
  FastAPI background task (U2 FD post-review R-01, NFD post-review R-03 and R-11):

  1. the task opens its **own** database session from the session factory;
  2. it issues the code (generate, hash, supersede, insert) with the cooldown already
     reserved by the request, and commits;
  3. it sends through the U1 email dispatcher (bulkhead + 25 s budget, retries), which runs
     the blocking sender off the event loop;
  4. on a final failure it supersedes **that code id only**, so a newer code is never
     cancelled, and logs at ERROR (``vendor.failed`` from the dispatcher). ``last_sent_at``
     is not reset, so the 60 s cooldown still holds and stops a send-failure loop.

A background task has no caller to report to, so every failure is logged, never raised.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import partial

import anyio.to_thread
from sqlalchemy.orm import Session

from app.identity.codes import CodeCooldownError, CodeLockedError, CodeService, IssuedCode
from app.identity.models import CodePurpose
from app.platform.db import SessionFactory
from app.platform.email.dispatch import EmailDispatcher
from app.platform.email.port import EmailTemplate
from app.platform.errors import AppError
from app.platform.metrics import Metrics
from app.platform.ratelimit import RateLimiter

logger = logging.getLogger("identity.delivery")

EMAIL_CAP_KEY = "email:global"
EMAIL_CAP_WINDOW_SECONDS = 3600
TEMPLATES: dict[CodePurpose, EmailTemplate] = {
    CodePurpose.SIGNUP: EmailTemplate.SIGNUP_CODE,
    CodePurpose.LOGIN: EmailTemplate.LOGIN_CODE,
    CodePurpose.PASSWORD_RESET: EmailTemplate.PASSWORD_RESET_CODE,
}


@dataclass(frozen=True)
class CodeSent:
    """The 202 reply after a code request (contract ``CodeSent``; no token, no cookie)."""

    masked_email: str
    resend_available_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class PendingCode:
    """A code to issue and email after the response (the account is known to be eligible)."""

    user_id: uuid.UUID
    email: str
    full_name: str
    purpose: CodePurpose


class CodeDelivery:
    """Issues and emails codes in a background task with its own database session.

    Args:
        session_factory: Factory for the task's own session (never the request's).
        codes: The OTP service.
        dispatcher: The U1 email dispatcher (bulkhead, budget, retries).
        limiter: Rate limiter used for the global hourly email cap.
        metrics: Metric series.
        email_hourly_cap: Global cap on code emails per hour.
    """

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        codes: CodeService,
        dispatcher: EmailDispatcher,
        limiter: RateLimiter,
        metrics: Metrics,
        email_hourly_cap: int,
    ) -> None:
        self._session_factory = session_factory
        self._codes = codes
        self._dispatcher = dispatcher
        self._limiter = limiter
        self._metrics = metrics
        self._email_hourly_cap = email_hourly_cap

    async def deliver(self, pending: PendingCode) -> None:
        """Issue and send one code. Never raises: every failure is logged."""
        try:
            issued = await anyio.to_thread.run_sync(self._issue_tx, pending)
        except (CodeLockedError, CodeCooldownError) as exc:
            logger.info(
                "code not sent",
                extra={
                    "event": "auth.code.not_sent",
                    "userId": str(pending.user_id),
                    "purpose": pending.purpose.value,
                    "errorClass": type(exc).__name__,
                },
            )
            return
        except Exception:
            logger.error(
                "background code issue failed",
                exc_info=True,
                extra={"event": "auth.code.issue_failed", "purpose": pending.purpose.value},
            )
            return
        await self._send(pending, issued)

    async def _send(self, pending: PendingCode, issued: IssuedCode) -> None:
        try:
            decision = await anyio.to_thread.run_sync(
                partial(
                    self._limiter.check_and_record,
                    EMAIL_CAP_KEY,
                    self._email_hourly_cap,
                    EMAIL_CAP_WINDOW_SECONDS,
                )
            )
            if not decision.allowed:
                logger.warning(
                    "hourly email cap reached", extra={"event": "auth.email_cap_reached"}
                )
                await anyio.to_thread.run_sync(self._supersede_tx, issued.code_id)
                return
            await self._dispatcher.send(
                pending.email, TEMPLATES[pending.purpose], self._vars(pending, issued)
            )
        except AppError:
            # The dispatcher already logged vendor.failed at ERROR with the failure class.
            await anyio.to_thread.run_sync(self._supersede_tx, issued.code_id)
            return
        self._metrics.auth_codes_sent_total.labels(purpose=pending.purpose.value).inc()
        logger.info(
            "code sent",
            extra={
                "event": "auth.code.sent",
                "userId": str(pending.user_id),
                "purpose": pending.purpose.value,
            },
        )

    def _vars(self, pending: PendingCode, issued: IssuedCode) -> dict[str, object]:
        return {
            "code": issued.code,
            "expires_minutes": int(self._codes.policy.ttl.total_seconds() // 60),
            "full_name": pending.full_name,
        }

    def _issue_tx(self, pending: PendingCode) -> IssuedCode:
        session: Session = self._session_factory()
        try:
            issued = self._codes.issue(
                session, pending.user_id, pending.purpose, cooldown_reserved=True
            )
            session.commit()
            return issued
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def _supersede_tx(self, code_id: uuid.UUID) -> None:
        """Supersede exactly this code (``consumed_at`` still empty), never a newer one."""
        session: Session = self._session_factory()
        try:
            self._codes.supersede(session, code_id)
            session.commit()
        except Exception:
            session.rollback()
            logger.error(
                "could not supersede an unsent code",
                exc_info=True,
                extra={"event": "auth.code.supersede_failed"},
            )
        finally:
            session.close()
