"""FastAPI dependencies for identity (contract C3, BR4.3, BR6.2, NFR2.8, NFR2.11, NFR3.4).

- :func:`current_user` validates the Bearer access token; it is applied to every
  protected router by default (secure by default).
- :func:`require_owner` turns "someone else's record" into 404, never 403.
- :func:`require_role` checks the role carried in the token.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.identity.services import AuthenticatedUser, IdentityService
from app.platform.errors import NotAuthenticated, NotFound

_bearer = HTTPBearer(auto_error=False, description="15-minute access token (AUTH-012)")


def get_identity(request: Request) -> IdentityService:
    """The identity service wired by the app factory."""
    service: IdentityService = request.app.state.identity
    return service


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> AuthenticatedUser:
    """Return the caller from a valid access token, or raise ``NOT_AUTHENTICATED``."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise NotAuthenticated()
    return get_identity(request).authenticate(credentials.credentials)


def require_owner(resource_user_id: uuid.UUID, user: AuthenticatedUser) -> None:
    """Refuse access to another user's record with 404 (hides existence; BR6.2).

    Raises:
        NotFound: When the record belongs to someone else.
    """
    if resource_user_id != user.user_id:
        raise NotFound()


def require_role(role: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Dependency factory: the caller must carry ``role`` (AUTH-008)."""

    def check(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:  # noqa: B008
        if user.role != role:
            raise NotFound()
        return user

    return check
