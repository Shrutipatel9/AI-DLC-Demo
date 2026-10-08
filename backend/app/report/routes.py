"""Report HTTP routes (contract C1 ``/report``, ``/report/pdf``; plan ``/home``).

Protected (mounted with ``current_user``), paywalled (402) and owner-only (404), always
``Cache-Control: no-store``. Handlers stay thin and call :class:`ReportService`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.platform.db import get_session
from app.platform.errors import error_responses
from app.report.dependencies import get_report_service, no_store
from app.report.schemas import HomeOut, ReportOut
from app.report.service import PDF_CONTENT_TYPE, ReportService

SessionDep = Annotated[Session, Depends(get_session)]
ReportDep = Annotated[ReportService, Depends(get_report_service)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]

router = APIRouter(tags=["report"], dependencies=[Depends(no_store)])

PDF_FILENAME = "facial-analysis-report.pdf"


@router.get(
    "/report",
    response_model=ReportOut,
    response_model_by_alias=True,
    responses=error_responses(401, 402, 404),
    summary="The published report: template text, assessments, 11 features, recommendations",
)
def get_report(user: UserDep, session: SessionDep, service: ReportDep) -> ReportOut:
    """402 without payment; 404 ``REPORT_NOT_READY`` while there is no report of your own."""
    return service.report(session, user.user_id)


@router.get(
    "/report/pdf",
    response_class=Response,
    responses={
        200: {"description": "The report PDF", "content": {PDF_CONTENT_TYPE: {}}},
        **error_responses(401, 402, 404),
    },
    summary="The report PDF: built on first download, then cached",
)
def get_report_pdf(user: UserDep, session: SessionDep, service: ReportDep) -> Response:
    """Same paywall and ownership as the report (US8.5)."""
    pdf = service.pdf(session, user.user_id)
    return Response(
        content=pdf.data,
        media_type=PDF_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{PDF_FILENAME}"'},
    )


@router.get(
    "/home",
    response_model=HomeOut,
    response_model_by_alias=True,
    responses=error_responses(401, 402, 404),
    summary="Home Overview data: stats, priorities, protocol, radar values",
)
def get_home(user: UserDep, session: SessionDep, service: ReportDep) -> HomeOut:
    """402 without payment; 404 ``REPORT_NOT_READY`` while there is no report (US11.1)."""
    return service.home(session, user.user_id)
