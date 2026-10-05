"""Auth HTTP routes (contract C1).

U1: /auth/register, /auth/login, /auth/verify, /auth/me.
U2: /auth/resend-code, /auth/refresh, /auth/logout, /auth/password/forgot,
/auth/password/verify-code, /auth/password/reset, /auth/change-password.

Route handlers stay thin: they validate input (schemas), apply the CSRF check and the
per-IP limiter, and call :class:`IdentityService` and the services it composes. They never
import the JWT or OTP services or the repositories directly (import-linter contract).

Cookie endpoints (refresh, logout) run CORS -> CSRF -> refresh limit -> handler. Every 401
from refresh clears the cookie; logout always clears it and answers 204. Non-revealing
endpoints answer first and send the code in a background task (equal response work).
"""

from __future__ import annotations

from functools import partial
from typing import Annotated

import anyio.to_thread
from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.identity.cookies import clear_cookie_params, refresh_cookie_params
from app.identity.dependencies import current_user, get_identity
from app.identity.schemas import (
    AccessTokenResponse,
    ChangePasswordRequest,
    CodeSentResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendRequest,
    ResetCodeVerifyRequest,
    ResetPasswordRequest,
    ResetTokenResponse,
    SessionResponse,
    UserResponse,
    VerifyRequest,
)
from app.identity.services import AccountInfo, AuthenticatedUser, CodeSent, IdentityService
from app.identity.sessions import Refused
from app.platform.csrf import RequireCsrf
from app.platform.db import get_session
from app.platform.errors import SessionInvalid, error_response, error_responses
from app.platform.ratelimit import PerIpLimit
from app.platform.settings import Settings

SessionDep = Annotated[Session, Depends(get_session)]
IdentityDep = Annotated[IdentityService, Depends(get_identity)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]


def _code_sent(result: CodeSent) -> CodeSentResponse:
    return CodeSentResponse(
        masked_email=result.masked_email,
        resend_available_at=result.resend_available_at,
        expires_at=result.expires_at,
    )


def _user(account: AccountInfo) -> UserResponse:
    return UserResponse(
        id=account.id,
        full_name=account.full_name,
        email=account.email,
        is_verified=account.is_verified,
        role="user",
        member_since=account.member_since,
    )


public_router = APIRouter(tags=["auth"])
protected_router = APIRouter(tags=["auth"])


@public_router.post(
    "/auth/register",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CodeSentResponse,
    response_model_by_alias=True,
    dependencies=[Depends(PerIpLimit("/auth/register"))],
    responses=error_responses(409, 422, 429, 502, 503, 504),
    summary="Step 1 of sign-up: create an unverified account and email a code",
)
async def register(
    body: RegisterRequest, session: SessionDep, identity: IdentityDep
) -> CodeSentResponse:
    """Create or refresh an unverified account and email a 6-digit code (no token)."""
    result = await identity.register(
        session, full_name=body.full_name, email=body.email, password=body.password
    )
    return _code_sent(result)


@public_router.post(
    "/auth/login",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CodeSentResponse,
    response_model_by_alias=True,
    dependencies=[Depends(PerIpLimit("/auth/login"))],
    responses=error_responses(401, 422, 429, 502, 503, 504),
    summary="Step 1 of login: check the password and email a code (no token)",
)
async def login(body: LoginRequest, session: SessionDep, identity: IdentityDep) -> CodeSentResponse:
    """Check email and password; on success email a login code."""
    result = await identity.login(session, email=body.email, password=body.password)
    return _code_sent(result)


@public_router.post(
    "/auth/verify",
    response_model=SessionResponse,
    response_model_by_alias=True,
    dependencies=[Depends(PerIpLimit("/auth/verify"))],
    responses=error_responses(401, 422, 429),
    summary="Step 2: verify the emailed code; returns the access token and sets the cookie",
)
async def verify(
    body: VerifyRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    identity: IdentityDep,
) -> SessionResponse:
    """Verify the code; set the httpOnly refresh cookie and return the access token."""
    signed_in = await identity.verify(
        session, email=body.email, code=body.code, purpose=body.purpose
    )
    settings = request.app.state.settings
    response.set_cookie(value=signed_in.refresh_token.value, **refresh_cookie_params(settings))
    return SessionResponse(
        access_token=signed_in.access_token,
        expires_at=signed_in.expires_at,
        user=_user(signed_in.account),
    )


@protected_router.get(
    "/auth/me",
    response_model=UserResponse,
    response_model_by_alias=True,
    responses=error_responses(401),
    summary="The signed-in user (AUTH-014)",
)
async def me(user: UserDep, session: SessionDep, identity: IdentityDep) -> UserResponse:
    """Return the signed-in user's profile."""
    account = await anyio.to_thread.run_sync(identity.account, session, user.user_id)
    return _user(account)


# ----------------------------------------------------------------------------- U2 routes


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@public_router.post(
    "/auth/resend-code",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CodeSentResponse,
    response_model_by_alias=True,
    dependencies=[Depends(PerIpLimit("/auth/resend-code"))],
    responses=error_responses(422, 429, 502, 503, 504),
    summary="Send a new code for an ongoing sign-up, login or reset (same reply for any email)",
)
async def resend_code(
    body: ResendRequest,
    background: BackgroundTasks,
    session: SessionDep,
    identity: IdentityDep,
) -> CodeSentResponse:
    """Resend a code (WF-U2-1); login and reset resends never reveal an account."""
    outcome = await identity.resend_code(session, email=body.email, purpose=body.purpose)
    if outcome.pending is not None:
        background.add_task(identity.delivery.deliver, outcome.pending)
    return _code_sent(outcome.reply)


@public_router.post(
    "/auth/refresh",
    response_model=AccessTokenResponse,
    response_model_by_alias=True,
    dependencies=[
        Depends(RequireCsrf("/auth/refresh", count_refresh=True)),
        Depends(PerIpLimit("/auth/refresh", kind="refresh")),
    ],
    responses=error_responses(401, 403, 429),
    summary="Exchange the refresh cookie for a new access token and rotate the cookie",
)
async def refresh(
    request: Request,
    session: SessionDep,
    identity: IdentityDep,
    x_refresh_attempt: Annotated[str | None, Header(max_length=64)] = None,
) -> Response:
    """Rotate the refresh session (WF-U2-5). Any refusal is 401 and clears the cookie."""
    settings = _settings(request)
    cookie = request.cookies.get(settings.refresh_cookie_name)
    result = await anyio.to_thread.run_sync(
        identity.sessions.refresh, session, cookie, x_refresh_attempt
    )
    if isinstance(result, Refused):
        refused = error_response(SessionInvalid(result.reason.value))
        refused.delete_cookie(**clear_cookie_params(settings))
        return refused
    body = AccessTokenResponse(access_token=result.access_token, expires_at=result.expires_at)
    response = JSONResponse(body.model_dump(mode="json", by_alias=True))
    response.set_cookie(value=result.refresh_token.value, **refresh_cookie_params(settings))
    return response


@public_router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[
        Depends(RequireCsrf("/auth/logout")),
        Depends(PerIpLimit("/auth/logout", kind="refresh")),
    ],
    responses=error_responses(403, 429),
    summary="Revoke the cookie's session family and clear the cookie",
)
async def logout(request: Request, session: SessionDep, identity: IdentityDep) -> Response:
    """Log out (WF-U2-6): revoke the whole family named by the cookie; always 204."""
    settings = _settings(request)
    cookie = request.cookies.get(settings.refresh_cookie_name)
    await anyio.to_thread.run_sync(identity.sessions.logout, session, cookie)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(**clear_cookie_params(settings))
    return response


@public_router.post(
    "/auth/password/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CodeSentResponse,
    response_model_by_alias=True,
    dependencies=[Depends(PerIpLimit("/auth/password/forgot"))],
    responses=error_responses(422, 429),
    summary="Request a reset code; always the same response (anti-enumeration)",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    background: BackgroundTasks,
    session: SessionDep,
    identity: IdentityDep,
) -> CodeSentResponse:
    """Request a password-reset code (WF-U2-7 step 1); the email is sent after the reply."""
    requested = await anyio.to_thread.run_sync(identity.password_reset.request, session, body.email)
    if requested.pending is not None:
        background.add_task(identity.delivery.deliver, requested.pending)
    return _code_sent(requested.reply)


@public_router.post(
    "/auth/password/verify-code",
    response_model=ResetTokenResponse,
    response_model_by_alias=True,
    dependencies=[Depends(PerIpLimit("/auth/password/verify-code"))],
    responses=error_responses(401, 422, 429),
    summary="Verify the reset code; returns a single-use reset token",
)
async def verify_reset_code(
    body: ResetCodeVerifyRequest, session: SessionDep, identity: IdentityDep
) -> ResetTokenResponse:
    """Verify a reset code (WF-U2-7 step 2)."""
    issued = await anyio.to_thread.run_sync(
        partial(identity.password_reset.verify_code, session, body.email, body.code)
    )
    return ResetTokenResponse(reset_token=issued.token, expires_at=issued.expires_at)


@public_router.post(
    "/auth/password/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(PerIpLimit("/auth/password/reset"))],
    responses=error_responses(401, 422, 429),
    summary="Set the new password with the reset token; revokes every session",
)
async def reset_password(
    body: ResetPasswordRequest, session: SessionDep, identity: IdentityDep
) -> Response:
    """Set a new password (WF-U2-7 step 3)."""
    await identity.password_reset.reset(session, body.reset_token, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@protected_router.post(
    "/auth/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(PerIpLimit("/auth/change-password"))],
    responses=error_responses(401, 422, 429),
    summary="Change the password; this session stays signed in, other sessions end",
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: UserDep,
    session: SessionDep,
    identity: IdentityDep,
) -> Response:
    """Change the signed-in user's password (WF-U2-8)."""
    cookie = request.cookies.get(_settings(request).refresh_cookie_name)
    await identity.password_change.change(
        session,
        user_id=user.user_id,
        current_password=body.current_password,
        new_password=body.new_password,
        cookie_value=cookie,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
