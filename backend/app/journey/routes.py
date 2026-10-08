"""``GET /journey/next-step`` (contract C1; US11.8). Protected, owner-only, never cached."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.journey.schemas import NextStepOut
from app.journey.service import JourneyService
from app.platform.db import get_session
from app.platform.errors import error_responses

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]


def get_journey(request: Request) -> JourneyService:
    """The journey service wired by the app factory."""
    service: JourneyService = request.app.state.journey
    return service


def no_store(response: Response) -> None:
    """Progress changes with every action: a browser or proxy must never cache it."""
    response.headers["Cache-Control"] = "no-store"


JourneyDep = Annotated[JourneyService, Depends(get_journey)]

router = APIRouter(tags=["journey"], dependencies=[Depends(no_store)])


@router.get(
    "/journey/next-step",
    response_model=NextStepOut,
    response_model_by_alias=True,
    responses=error_responses(401),
    summary="The user's next unfinished step (US11.8)",
)
def get_next_step(user: UserDep, session: SessionDep, journey: JourneyDep) -> NextStepOut:
    """Exactly one step per the AC11.8.1 table, recomputed on every call."""
    result = journey.next_step(session, user.user_id)
    return NextStepOut(step=result.step, flagged_angles=list(result.flagged_angles))
