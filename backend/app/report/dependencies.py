"""FastAPI dependencies for report routes."""

from __future__ import annotations

from fastapi import Request, Response

from app.report.service import ReportService


def get_report_service(request: Request) -> ReportService:
    """The report service wired by the app factory."""
    service: ReportService = request.app.state.report
    return service


def no_store(response: Response) -> None:
    """The report and the PDF are personal: never let a browser or proxy cache them."""
    response.headers["Cache-Control"] = "no-store"
