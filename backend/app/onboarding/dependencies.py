"""FastAPI dependencies for onboarding routes."""

from __future__ import annotations

from fastapi import Request, Response

from app.onboarding.services import OnboardingService


def get_onboarding(request: Request) -> OnboardingService:
    """The onboarding service wired by the app factory."""
    service: OnboardingService = request.app.state.onboarding
    return service


def no_store(response: Response) -> None:
    """Answers can hold health data: never let a browser or proxy cache them."""
    response.headers["Cache-Control"] = "no-store"
