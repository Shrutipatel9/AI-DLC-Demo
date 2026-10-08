"""FastAPI dependencies for analysis routes."""

from __future__ import annotations

from fastapi import Request, Response

from app.analysis.services import AnalysisService


def get_analysis(request: Request) -> AnalysisService:
    """The analysis service wired by the app factory."""
    service: AnalysisService = request.app.state.analysis
    return service


def no_store(response: Response) -> None:
    """Run state is personal: never let a browser or proxy cache it."""
    response.headers["Cache-Control"] = "no-store"
