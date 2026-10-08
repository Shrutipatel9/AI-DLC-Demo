"""The AnalysisPipeline module's public interface. Other modules import only this.

- ``build_analysis`` (API process): the start/read/re-run service from settings.
- ``build_pipeline`` (worker process): the pipeline with its built-in steps registered (C7), and
  ``JOB_KIND`` for the worker's handler table.
- ``router``: the ``/analysis/runs`` routes (mounted as protected routes).
- ``media_in_use``: tells the MediaStore a photo is referenced by a run's snapshot, so a retake
  does not delete it while the run may still need it (R-02; C8 ``retire``).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.analysis import repositories
from app.analysis.domain import JOB_KIND, STEP_KEYS, RunView
from app.analysis.pipeline import AnalysisPipeline, RunContext, StepHandler, StepResult
from app.analysis.routes import router
from app.analysis.services import AnalysisService
from app.analysis.steps import SLOT_COUNT, AnalysisSteps
from app.jobs.public import JobQueue
from app.measurement.public import MeasurementService
from app.media.public import MediaStore
from app.onboarding.public import OnboardingService
from app.payments.public import PaymentService
from app.photos.public import PhotoIntakeService
from app.platform.clock import Clock
from app.platform.db import SessionFactory
from app.platform.settings import Settings
from app.report_writing.public import ReportWritingService

__all__ = [
    "JOB_KIND",
    "SLOT_COUNT",
    "STEP_KEYS",
    "AnalysisPipeline",
    "AnalysisService",
    "RunContext",
    "RunView",
    "StepHandler",
    "StepResult",
    "build_analysis",
    "build_pipeline",
    "media_in_use",
    "router",
]


def build_analysis(
    settings: Settings,
    *,
    clock: Clock,
    queue: JobQueue,
    payments: PaymentService,
    photos: PhotoIntakeService,
) -> AnalysisService:
    """Create the API-side analysis service from settings."""
    return AnalysisService(
        queue=queue,
        payments=payments,
        photos=photos,
        clock=clock,
        expected_wait_minutes=settings.analysis_expected_wait_minutes,
    )


def build_pipeline(
    settings: Settings,
    *,
    clock: Clock,
    session_factory: SessionFactory,
    media: MediaStore,
    measurement: MeasurementService,
    onboarding: OnboardingService,
    report_writing: ReportWritingService,
) -> AnalysisPipeline:
    """Create the worker-side pipeline with the built-in steps registered (C7)."""
    pipeline = AnalysisPipeline(session_factory=session_factory, clock=clock)
    AnalysisSteps(
        media=media,
        measurement=measurement,
        onboarding=onboarding,
        report_writing=report_writing,
        clock=clock,
        distress_trigger=settings.tone_distress_trigger,
        frequency_trigger=settings.tone_frequency_trigger,
    ).register(pipeline)
    return pipeline


def media_in_use(session: Session, file_id: uuid.UUID) -> bool:
    """Whether a run was started with this photo file (the MediaStore reference check)."""
    return repositories.media_in_use(session, file_id)
