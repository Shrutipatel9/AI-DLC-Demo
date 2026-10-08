"""Analysis HTTP routes (contract C1 ``/analysis/runs``; US7.1, US7.2, US7.11).

All routes are protected (mounted with ``current_user``) and send ``Cache-Control: no-store``.
Handlers stay thin and call :class:`AnalysisService`; they never touch repositories or models.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analysis.dependencies import get_analysis, no_store
from app.analysis.schemas import AnalysisRunOut, to_out
from app.analysis.services import AnalysisService
from app.identity.public import AuthenticatedUser, current_user
from app.platform.db import get_session
from app.platform.errors import error_responses

SessionDep = Annotated[Session, Depends(get_session)]
AnalysisDep = Annotated[AnalysisService, Depends(get_analysis)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]

router = APIRouter(tags=["analysis"], dependencies=[Depends(no_store)])


@router.post(
    "/analysis/runs",
    status_code=202,
    response_model=AnalysisRunOut,
    response_model_by_alias=True,
    responses=error_responses(401, 402, 409),
    summary='"Start Analysis": idempotent; a second call returns the same run',
)
def post_start(user: UserDep, session: SessionDep, analysis: AnalysisDep) -> AnalysisRunOut:
    """402 first, then 409 for a photo set that is not consistent now, then the run (US7.1)."""
    return to_out(analysis.start(session, user.user_id))


@router.get(
    "/analysis/runs/current",
    response_model=AnalysisRunOut,
    response_model_by_alias=True,
    responses=error_responses(401, 404),
    summary="The current run's steps and state (polled every 2-3 s)",
)
def get_current(user: UserDep, session: SessionDep, analysis: AnalysisDep) -> AnalysisRunOut:
    """Steps (done, current, waiting), expected wait, failure and re-run availability (US7.2)."""
    return to_out(analysis.current(session, user.user_id))


@router.post(
    "/analysis/runs/current/rerun",
    status_code=202,
    response_model=AnalysisRunOut,
    response_model_by_alias=True,
    responses=error_responses(401, 404, 409),
    summary="The one free re-run after a failed run",
)
def post_rerun(user: UserDep, session: SessionDep, analysis: AnalysisDep) -> AnalysisRunOut:
    """409 ``RERUN_NOT_AVAILABLE`` when the run has not failed or the re-run was used (US7.11)."""
    return to_out(analysis.rerun(session, user.user_id))
