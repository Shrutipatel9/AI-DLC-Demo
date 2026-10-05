"""The identity module's public interface (contract C3). Other modules import only this.

- ``current_user`` / ``AuthenticatedUser``: the auth dependency every later unit uses.
- ``require_owner`` / ``require_role``: reusable authorisation checks.
- ``build_identity``: wires the identity service from settings (used by the app factory).
- ``public_router`` / ``protected_router``: the auth routes.
"""

from __future__ import annotations

from datetime import timedelta

from app.identity.codes import CodePolicy, CodeService
from app.identity.delivery import CodeDelivery
from app.identity.dependencies import current_user, require_owner, require_role
from app.identity.password_change import PasswordChangeService
from app.identity.password_reset import PasswordResetService
from app.identity.passwords import Argon2Params, PasswordHasher
from app.identity.routes import protected_router, public_router
from app.identity.services import AccountInfo, AuthenticatedUser, IdentityConfig, IdentityService
from app.identity.sessions import SessionPolicy, SessionService
from app.identity.shadow import ShadowCounters
from app.identity.tokens import TokenService
from app.platform.clock import Clock
from app.platform.db import SessionFactory
from app.platform.email.dispatch import EmailDispatcher
from app.platform.metrics import Metrics
from app.platform.ratelimit import RateLimiter
from app.platform.settings import Settings

__all__ = [
    "AccountInfo",
    "AuthenticatedUser",
    "IdentityService",
    "build_identity",
    "current_user",
    "protected_router",
    "public_router",
    "require_owner",
    "require_role",
]


def build_identity(
    settings: Settings,
    *,
    clock: Clock,
    dispatcher: EmailDispatcher,
    limiter: RateLimiter,
    metrics: Metrics,
    session_factory: SessionFactory,
) -> IdentityService:
    """Create the identity service and its collaborators from settings.

    ``session_factory`` gives background code deliveries their own database session.

    Raises:
        app.identity.tokens.TokenConfigError: On an unsafe signing-key configuration.
    """
    hasher = PasswordHasher(
        Argon2Params(
            memory_kib=settings.argon2_memory_kib,
            time_cost=settings.argon2_time_cost,
            parallelism=settings.argon2_parallelism,
        )
    )
    policy = CodePolicy(
        ttl=timedelta(seconds=settings.code_ttl_seconds),
        cooldown=timedelta(seconds=settings.code_resend_cooldown_seconds),
        max_failures=settings.code_max_failures,
        lock_duration=timedelta(seconds=settings.code_lock_seconds),
    )
    codes = CodeService(hmac_key=settings.code_key(), clock=clock, policy=policy)
    tokens = TokenService.from_settings(settings, clock)
    sessions = SessionService(
        clock=clock,
        tokens=tokens,
        policy=SessionPolicy(
            ttl=timedelta(seconds=settings.refresh_token_ttl_seconds),
            recovery_window=timedelta(seconds=settings.refresh_attempt_recovery_seconds),
        ),
        metrics=metrics,
    )
    shadow = ShadowCounters(key=settings.email_key(), clock=clock, policy=policy)
    return IdentityService(
        config=IdentityConfig(email_hourly_cap=settings.auth_email_hourly_cap),
        clock=clock,
        hasher=hasher,
        codes=codes,
        tokens=tokens,
        dispatcher=dispatcher,
        limiter=limiter,
        metrics=metrics,
        sessions=sessions,
        shadow=shadow,
        delivery=CodeDelivery(
            session_factory=session_factory,
            codes=codes,
            dispatcher=dispatcher,
            limiter=limiter,
            metrics=metrics,
            email_hourly_cap=settings.auth_email_hourly_cap,
        ),
        password_reset=PasswordResetService(
            clock=clock,
            codes=codes,
            shadow=shadow,
            sessions=sessions,
            hasher=hasher,
            token_ttl=timedelta(minutes=settings.reset_token_minutes),
            metrics=metrics,
        ),
        password_change=PasswordChangeService(
            clock=clock, hasher=hasher, sessions=sessions, metrics=metrics
        ),
    )
