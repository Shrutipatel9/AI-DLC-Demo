"""FastAPI dependencies for photo routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.onboarding.public import OnboardingService, require_submitted_questionnaire
from app.photos.services import PhotoIntakeService
from app.platform.db import get_session


def get_photos(request: Request) -> PhotoIntakeService:
    """The PhotoIntake service wired by the app factory."""
    service: PhotoIntakeService = request.app.state.photos
    return service


def no_store(response: Response) -> None:
    """Photo data is personal: never let a browser or proxy cache it."""
    response.headers["Cache-Control"] = "no-store"


def questionnaire_submitted(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Photos come after the questionnaire (409 ``QUESTIONNAIRE_NOT_SUBMITTED``; U3 port)."""
    onboarding: OnboardingService = request.app.state.onboarding
    require_submitted_questionnaire(onboarding, session, user.user_id)
