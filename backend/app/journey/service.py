"""Journey service: reads each stateful module's public port, then applies the rule."""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy.orm import Session

from app.analysis.public import latest_result_view, latest_run_ref
from app.journey.rule import NextStep, PaymentState, Progress, RunStatus, next_step
from app.onboarding.public import OnboardingService, get_onboarding_state
from app.payments.public import PaymentService, payment_state
from app.photos.public import PhotoIntakeService, get_photo_set_state


class JourneyService:
    """Computes the user's next step from live state; nothing is cached (AC11.8.1)."""

    def __init__(
        self,
        *,
        onboarding: OnboardingService,
        photos: PhotoIntakeService,
        payments: PaymentService,
    ) -> None:
        self.onboarding = onboarding
        self.photos = photos
        self.payments = payments

    def next_step(self, session: Session, user_id: uuid.UUID) -> NextStep:
        """The single next unfinished step, recomputed on every call."""
        onboarding = get_onboarding_state(self.onboarding, session, user_id)
        if not onboarding.consented or not onboarding.submitted:
            return next_step(Progress(onboarding.consented, onboarding.submitted, False, False))
        photo_state = get_photo_set_state(self.photos, session, user_id)
        pay: PaymentState = payment_state(self.payments, session, user_id)
        run = latest_run_ref(session, user_id)
        report = pay == "paid" and latest_result_view(session, user_id) is not None
        return next_step(
            Progress(
                consented=True,
                submitted=True,
                photos_complete=photo_state.complete,
                photos_consistent=photo_state.consistent,
                flagged_angles=photo_state.flagged_angles,
                payment=pay,
                run_status=cast(RunStatus, run.status) if run is not None else None,
                report_exists=report,
            )
        )
