"""The Journey module's public interface. Other modules import only this.

- ``build_journey``: the service from the onboarding, photo and payment services.
- ``router``: ``/journey/next-step`` (mounted as a protected route).
"""

from __future__ import annotations

from app.journey.routes import router
from app.journey.service import JourneyService
from app.onboarding.public import OnboardingService
from app.payments.public import PaymentService
from app.photos.public import PhotoIntakeService

__all__ = ["JourneyService", "build_journey", "router"]


def build_journey(
    *, onboarding: OnboardingService, photos: PhotoIntakeService, payments: PaymentService
) -> JourneyService:
    """Create the journey service."""
    return JourneyService(onboarding=onboarding, photos=photos, payments=payments)
