"""Identity application service: sign-up, login, code verification, resend and "who am I".

Workflows WF-U1-1 to WF-U1-5 (U1) and WF-U2-1 (resend, U2). Rules BR1.x-BR4.x (U1) and
BR1.1-BR1.6 (U2). It also composes the U2 services the routes call: refresh sessions
(:attr:`IdentityService.sessions`), password reset and password change.

Email delivery follows commit -> send -> compensate (reliability design section 2,
NFR5.13): the code is committed in a short transaction (tx1) and the connection is
released; the email is sent with no connection or row lock held; on final failure a
second short transaction (tx2) supersedes the code, so it can never be verified, and
the user can ask again after the cooldown.

Blocking work (database, Argon2) runs in AnyIO's default thread pool. Email sends run
behind the dedicated email bulkhead in :class:`EmailDispatcher`.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial

import anyio.to_thread
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.identity import repositories as repo
from app.identity.codes import (
    CodeCooldownError,
    CodeLockedError,
    CodeService,
    IssuedCode,
    VerifyResult,
    VerifyStatus,
    reset_expired_lock,
)
from app.identity.cookies import RefreshToken
from app.identity.delivery import (
    EMAIL_CAP_KEY,
    EMAIL_CAP_WINDOW_SECONDS,
    TEMPLATES,
    CodeDelivery,
    CodeSent,
    PendingCode,
)
from app.identity.models import CodePurpose, User
from app.identity.password_change import PasswordChangeService
from app.identity.password_reset import PasswordResetService
from app.identity.passwords import PasswordHasher
from app.identity.sessions import SessionService
from app.identity.shadow import ShadowCounters, normalise_email
from app.identity.tokens import InvalidTokenError, TokenService
from app.platform.clock import Clock
from app.platform.email.dispatch import EmailDispatcher
from app.platform.errors import (
    AppError,
    CodeExpired,
    CodeInvalid,
    CodeLocked,
    CodeResendCooldown,
    EmailAlreadyRegistered,
    InvalidCredentials,
    NotAuthenticated,
    UpstreamUnavailable,
)
from app.platform.logging import mask_email
from app.platform.metrics import Metrics
from app.platform.ratelimit import RateLimiter

logger = logging.getLogger("identity")

__all__ = ["AccountInfo", "AuthenticatedUser", "CodeSent", "IdentityService", "ResendOutcome"]

#: A login or reset resend is honoured only within 10 minutes of the step that started
#: the flow (BR1.6, [Decided by delivery team]); measured from ``flow_started_at`` (R-06).
RESEND_FLOW_WINDOW = timedelta(minutes=10)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Who is calling, from a verified access token (contract C3)."""

    user_id: uuid.UUID
    role: str


@dataclass(frozen=True)
class AccountInfo:
    """Public view of an account (``/auth/me``, contract C3 ``get_account``)."""

    id: uuid.UUID
    full_name: str
    email: str
    is_verified: bool
    role: str
    member_since: datetime


@dataclass(frozen=True)
class ResendOutcome:
    """The resend reply and, for a non-revealing purpose, a code to send after it."""

    reply: CodeSent
    pending: PendingCode | None = field(default=None, repr=False)


@dataclass(frozen=True)
class SignedIn:
    """What a successful verification returns."""

    access_token: str
    expires_at: datetime
    account: AccountInfo
    refresh_token: RefreshToken


@dataclass(frozen=True)
class _PendingDelivery:
    user_id: uuid.UUID
    email: str
    full_name: str
    purpose: CodePurpose
    issued: IssuedCode


@dataclass(frozen=True)
class IdentityConfig:
    """Tunables from settings."""

    email_hourly_cap: int = 500


def _account(user: User) -> AccountInfo:
    return AccountInfo(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        is_verified=user.is_verified,
        role=user.role,
        member_since=user.created_at,
    )


async def _in_thread[T](func: Callable[[], T]) -> T:
    return await anyio.to_thread.run_sync(func)


class IdentityService:
    """Orchestrates the identity workflows.

    Args:
        config: Tunables (email cap).
        clock: Time source.
        hasher: Argon2id password hasher.
        codes: One-time code service.
        tokens: Access-token service.
        dispatcher: Email dispatcher (bulkhead + budget).
        limiter: Rate limiter used for the global hourly email cap.
        metrics: Metric series.
        sessions: Refresh-session service (U2).
        shadow: Shadow counters for unknown emails (U2).
        delivery: Background code delivery for the non-revealing endpoints (U2).
        password_reset: Forgot/verify-code/reset service (U2).
        password_change: Signed-in password change service (U2).
    """

    def __init__(
        self,
        *,
        config: IdentityConfig,
        clock: Clock,
        hasher: PasswordHasher,
        codes: CodeService,
        tokens: TokenService,
        dispatcher: EmailDispatcher,
        limiter: RateLimiter,
        metrics: Metrics,
        sessions: SessionService,
        shadow: ShadowCounters,
        delivery: CodeDelivery,
        password_reset: PasswordResetService,
        password_change: PasswordChangeService,
    ) -> None:
        self._config = config
        self._clock = clock
        self._hasher = hasher
        self._codes = codes
        self._tokens = tokens
        self._dispatcher = dispatcher
        self._limiter = limiter
        self._metrics = metrics
        self._shadow = shadow
        self.sessions = sessions
        self.delivery = delivery
        self.password_reset = password_reset
        self.password_change = password_change

    # ------------------------------------------------------------------ sign-up (WF-U1-1)

    async def register(
        self, session: Session, *, full_name: str, email: str, password: str
    ) -> CodeSent:
        """Create or refresh an unverified account and email a sign-up code.

        Raises:
            EmailAlreadyRegistered: The email belongs to a verified account (BR1.3).
            CodeResendCooldown: Re-sign-up within 60 s of the last code (BR1.4, BR2.6).
            UpstreamUnavailable, UpstreamTimeout: The email could not be sent.
        """
        logger.info(
            "sign-up requested",
            extra={"event": "auth.signup.requested", "email": mask_email(email)},
        )
        password_hash = await _in_thread(partial(self._hasher.hash, password))
        try:
            pending = await _in_thread(
                partial(self._register_tx, session, full_name, email, password_hash)
            )
        except IntegrityError:
            # A concurrent sign-up created the same email first; retry once, which
            # takes the "already registered" or cooldown path.
            await _in_thread(session.rollback)
            pending = await _in_thread(
                partial(self._register_tx, session, full_name, email, password_hash)
            )
        return await self._deliver(session, pending)

    def _register_tx(
        self, session: Session, full_name: str, email: str, password_hash: str
    ) -> _PendingDelivery:
        now = self._clock.now()
        try:
            user = repo.find_user_by_email(session, email, for_update=True)
            if user is not None and user.is_verified:
                raise EmailAlreadyRegistered()
            if user is None:
                user = repo.add_user(
                    session, full_name=full_name, email=email, password_hash=password_hash, now=now
                )
            else:
                user.full_name = full_name
                user.password_hash = password_hash
                user.updated_at = now
            issued = self._issue(session, user.id, CodePurpose.SIGNUP)
            self._start_flow(session, user.id, CodePurpose.SIGNUP, now)
            session.commit()
        except BaseException:
            session.rollback()
            raise
        return _PendingDelivery(user.id, user.email, user.full_name, CodePurpose.SIGNUP, issued)

    # ------------------------------------------------------------------ login (WF-U1-3)

    async def login(self, session: Session, *, email: str, password: str) -> CodeSent:
        """Check the password and email a login code. Issues no token (BR3.2).

        Step order (U2 NFD post-review R-04): look up the user, check the password (dummy
        hash for unknown users), answer ``INVALID_CREDENTIALS`` on any failure, and only
        after a correct password check the login lockout. So the lockout reveals nothing
        to someone who does not know the password.

        Raises:
            InvalidCredentials: Unknown, unverified or wrong password - same answer (BR3.1).
            CodeLocked: Login-code verification is locked (only after a correct password).
            CodeResendCooldown: Within 60 s of the last login code.
        """
        pending = await _in_thread(partial(self._login_tx, session, email, password))
        return await self._deliver(session, pending)

    def _login_tx(self, session: Session, email: str, password: str) -> _PendingDelivery:
        try:
            user = repo.find_user_by_email(session, email)
            if user is None or not user.is_verified:
                self._hasher.verify_dummy(password)
                self._login_failed(email)
            assert user is not None  # noqa: S101  (narrowing; _login_failed always raises)
            ok, new_hash = self._hasher.verify_and_maybe_rehash(user.password_hash, password)
            if not ok:
                self._login_failed(email)
            if new_hash is not None:
                user.password_hash = new_hash
                user.updated_at = self._clock.now()
            issued = self._issue(session, user.id, CodePurpose.LOGIN)
            self._start_flow(session, user.id, CodePurpose.LOGIN, self._clock.now())
            session.commit()
        except BaseException:
            session.rollback()
            raise
        logger.info(
            "login code requested", extra={"event": "auth.login.code_sent", "userId": str(user.id)}
        )
        return _PendingDelivery(user.id, user.email, user.full_name, CodePurpose.LOGIN, issued)

    @staticmethod
    def _login_failed(email: str) -> None:
        logger.info(
            "login failed", extra={"event": "auth.login.failed", "email": mask_email(email)}
        )
        raise InvalidCredentials()

    # ------------------------------------------------------------------ verify (WF-U1-2)

    async def verify(self, session: Session, *, email: str, code: str, purpose: str) -> SignedIn:
        """Verify an emailed code; on success sign the user in.

        Raises:
            CodeInvalid: Wrong, used, superseded or unknown (with ``attemptsLeft`` when known).
            CodeExpired: The code is 10 minutes old or older.
            CodeLocked: Five failures; locked for 15 minutes.
        """
        return await _in_thread(
            partial(self._verify_tx, session, email, code, CodePurpose(purpose))
        )

    def _verify_tx(self, session: Session, email: str, code: str, purpose: CodePurpose) -> SignedIn:
        try:
            user = repo.find_user_by_email(session, email)
            if user is None and purpose is CodePurpose.LOGIN:
                # Unknown email: count on an email-keyed shadow counter, so it locks after
                # five wrong codes exactly like a real account (U2 FD post-review R-01).
                self._codes.dummy_hash(purpose, code)
                result = self._shadow.fail(session, self._shadow.email_hash(email), purpose)
            else:
                result = self._codes.verify(session, user.id if user else None, purpose, code)
            if result.status is not VerifyStatus.OK or user is None:
                session.commit()  # failure counts must persist (BR2.7)
                raise self._verify_error(result, user, purpose)
            now = self._clock.now()
            if purpose is CodePurpose.SIGNUP and not user.is_verified:
                user.is_verified = True
                user.verified_at = now
                user.updated_at = now
            refresh = self.sessions.start(session, user.id)
            access = self._tokens.issue_access(user.id, user.role)
            session.commit()
        except BaseException:
            session.rollback()
            raise
        logger.info(
            "code verified",
            extra={"event": "auth.verified", "userId": str(user.id), "purpose": purpose.value},
        )
        return SignedIn(access.token, access.expires_at, _account(user), refresh)

    def _verify_error(
        self, result: VerifyResult, user: User | None, purpose: CodePurpose
    ) -> AppError:
        user_id = str(user.id) if user else None
        if result.status is VerifyStatus.EXPIRED:
            return CodeExpired()
        if result.status is VerifyStatus.LOCKED:
            if result.locked_now:
                self._metrics.auth_lockouts_total.labels(purpose=purpose.value).inc()
                self._metrics.auth_code_failures_total.labels(purpose=purpose.value).inc()
                logger.warning(
                    "code verification locked",
                    extra={
                        "event": "auth.code.locked",
                        "userId": user_id,
                        "purpose": purpose.value,
                    },
                )
            return CodeLocked(retry_after=result.retry_after)
        if result.attempts_left is not None:
            self._metrics.auth_code_failures_total.labels(purpose=purpose.value).inc()
            logger.info(
                "wrong code",
                extra={
                    "event": "auth.code.failed",
                    "userId": user_id,
                    "purpose": purpose.value,
                    "attemptsLeft": result.attempts_left,
                },
            )
        return CodeInvalid(attempts_left=result.attempts_left)

    # ------------------------------------------------------------------ resend (WF-U2-1)

    async def resend_code(self, session: Session, *, email: str, purpose: str) -> ResendOutcome:
        """Send a new code for an ongoing flow (BR1.1-BR1.6, U2 FD post-review R-01).

        - ``signup``: visible. A real unverified account gets a new code now (U1 delivery),
          or 429 ``CODE_RESEND_COOLDOWN`` / ``CODE_LOCKED``. Any other email gets the same
          202 shape and nothing is sent (BR1.5).
        - ``login`` and ``password_reset``: non-revealing. Every branch does the same work
          and gets the identical 202; only an eligible account (verified, flow started in
          the last 10 minutes, not locked, past the cooldown) gets a ``pending`` code that
          the route sends after the response.

        Raises:
            CodeResendCooldown: Sign-up resend within 60 s (visible purpose only).
            CodeLocked: Sign-up verification is locked (visible purpose only).
            UpstreamUnavailable, UpstreamTimeout: The sign-up email could not be sent.
        """
        code_purpose = CodePurpose(purpose)
        normalised = normalise_email(email)
        if code_purpose is CodePurpose.SIGNUP:
            pending = await _in_thread(partial(self._signup_resend_tx, session, normalised))
            if pending is None:
                return ResendOutcome(self._generic_reply(normalised))
            return ResendOutcome(await self._deliver(session, pending))
        reserved = await _in_thread(
            partial(self._quiet_resend_tx, session, normalised, code_purpose)
        )
        return ResendOutcome(self._generic_reply(normalised), reserved)

    def _signup_resend_tx(self, session: Session, email: str) -> _PendingDelivery | None:
        try:
            user = repo.find_user_by_email(session, email)
            if user is None or user.is_verified:
                self._codes.dummy_hash(CodePurpose.SIGNUP, "000000")
                session.commit()
                return None
            issued = self._issue(session, user.id, CodePurpose.SIGNUP)
            session.commit()
        except BaseException:
            session.rollback()
            raise
        return _PendingDelivery(user.id, user.email, user.full_name, CodePurpose.SIGNUP, issued)

    def _quiet_resend_tx(
        self, session: Session, email: str, purpose: CodePurpose
    ) -> PendingCode | None:
        """Same work on every branch: email HMAC, one counter upsert, a dummy code HMAC."""
        now = self._clock.now()
        email_hash = self._shadow.email_hash(email)
        self._codes.dummy_hash(purpose, "000000")
        try:
            user = repo.find_user_by_email(session, email)
            if user is not None and user.is_verified:
                pending = self._reserve_resend(session, user, purpose, now)
            else:
                self._shadow.touch(session, email_hash, purpose)
                pending = None
            session.commit()
        except BaseException:
            session.rollback()
            raise
        return pending

    def _reserve_resend(
        self, session: Session, user: User, purpose: CodePurpose, now: datetime
    ) -> PendingCode | None:
        counter = repo.lock_counter(session, user.id, purpose)
        reset_expired_lock(counter, now)
        in_flow = (
            counter.flow_started_at is not None
            and now - counter.flow_started_at <= RESEND_FLOW_WINDOW
        )
        locked = counter.locked_until is not None and counter.locked_until > now
        cooling = (
            counter.last_sent_at is not None
            and now < counter.last_sent_at + self._codes.policy.cooldown
        )
        if not in_flow or locked or cooling:
            session.flush()
            return None
        counter.last_sent_at = now
        session.flush()
        return PendingCode(user.id, user.email, user.full_name, purpose)

    def _generic_reply(self, email: str) -> CodeSent:
        now = self._clock.now()
        return CodeSent(
            masked_email=mask_email(email) or "",
            resend_available_at=now + self._codes.policy.cooldown,
            expires_at=now + self._codes.policy.ttl,
        )

    @staticmethod
    def _start_flow(
        session: Session, user_id: uuid.UUID, purpose: CodePurpose, now: datetime
    ) -> None:
        """Record when this flow started; a resend never moves it (BR1.6, R-06)."""
        counter = repo.lock_counter(session, user_id, purpose)
        counter.flow_started_at = now
        session.flush()

    # ------------------------------------------------------------------ who am I (WF-U1-5)

    def authenticate(self, token: str) -> AuthenticatedUser:
        """Validate an access token (BR4.3).

        Raises:
            NotAuthenticated: For any invalid token.
        """
        try:
            claims = self._tokens.verify_access(token)
        except InvalidTokenError as exc:
            raise NotAuthenticated() from exc
        return AuthenticatedUser(user_id=claims.user_id, role=claims.role)

    def account(self, session: Session, user_id: uuid.UUID) -> AccountInfo:
        """Return the signed-in user's account (BR4.4).

        Raises:
            NotAuthenticated: The token's user no longer exists.
        """
        user = repo.get_user(session, user_id)
        if user is None:
            raise NotAuthenticated()
        return _account(user)

    # ------------------------------------------------------------------ helpers

    def _issue(self, session: Session, user_id: uuid.UUID, purpose: CodePurpose) -> IssuedCode:
        try:
            return self._codes.issue(session, user_id, purpose)
        except CodeCooldownError as exc:
            raise CodeResendCooldown(retry_after=exc.retry_after) from exc
        except CodeLockedError as exc:
            raise CodeLocked(retry_after=exc.retry_after) from exc

    async def _deliver(self, session: Session, pending: _PendingDelivery) -> CodeSent:
        """Send the code email after commit; supersede the code if it cannot be sent."""
        try:
            decision = await _in_thread(
                partial(
                    self._limiter.check_and_record,
                    EMAIL_CAP_KEY,
                    self._config.email_hourly_cap,
                    EMAIL_CAP_WINDOW_SECONDS,
                )
            )
            if not decision.allowed:
                logger.warning(
                    "hourly email cap reached", extra={"event": "auth.email_cap_reached"}
                )
                raise UpstreamUnavailable(status_code=503)
            variables = {
                "code": pending.issued.code,
                "expires_minutes": int(self._codes.policy.ttl.total_seconds() // 60),
                "full_name": pending.full_name,
            }
            await self._dispatcher.send(pending.email, TEMPLATES[pending.purpose], variables)
        except AppError:
            await _in_thread(partial(self._compensate, session, pending.issued.code_id))
            raise
        self._metrics.auth_codes_sent_total.labels(purpose=pending.purpose.value).inc()
        logger.info(
            "code sent",
            extra={
                "event": "auth.code.sent",
                "userId": str(pending.user_id),
                "purpose": pending.purpose.value,
            },
        )
        return CodeSent(
            masked_email=mask_email(pending.email) or "",
            resend_available_at=pending.issued.resend_available_at,
            expires_at=pending.issued.expires_at,
        )

    def _compensate(self, session: Session, code_id: uuid.UUID) -> None:
        """tx2: supersede a code whose email failed, so it can never be verified."""
        try:
            self._codes.supersede(session, code_id)
            session.commit()
        except BaseException:
            session.rollback()
            raise
