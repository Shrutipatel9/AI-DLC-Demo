"""Image fixtures: the analysis fixtures plus a worker pipeline whose image step uses the
recording image FAKE (never OpenAI), with no waiting between rate-limit retries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fakes import FakeImageEditor, FakeTextModel
from app.analysis.public import JOB_KIND, build_pipeline
from app.images.public import (
    ImageGenerationService,
    build_image_generation,
    register_image_step,
)
from app.jobs.public import Worker
from app.measurement.public import build_measurement
from app.platform.clock import FrozenClock
from app.report_writing.public import build_report_writing
from tests.analysis.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    Harness,
    app,
    client,
    consistent,
    email_fake,
    fake_gateway,
    insert_payment,
    make_paid_user,
    media_root,
    paid,
    seed_definition,
    settings_overrides,
    submitted,
    text_model,
    upload_consistent_set,
    webhooks,
)


@dataclass
class ImageHarness(Harness):
    """The analysis harness with the real image step on a recording image fake."""

    editor: FakeImageEditor = field(default_factory=FakeImageEditor)
    images: ImageGenerationService | None = None
    sleeps: list[float] = field(default_factory=list)


@pytest.fixture
def image_harness(
    app: FastAPI,  # noqa: F811
    client: TestClient,  # noqa: F811  (starts the app so the face model is loaded)
    session_factory: Callable[[], Session],
    frozen_clock: FrozenClock,
    text_model: FakeTextModel,  # noqa: F811
) -> ImageHarness:
    # One image at a time: the tests share one rolled-back connection (no concurrent savepoints).
    settings = app.state.settings.model_copy(update={"ai_image_concurrency": 1})
    pipeline = build_pipeline(
        settings,
        clock=frozen_clock,
        session_factory=session_factory,
        media=app.state.media,
        measurement=build_measurement(settings, geometry=app.state.face_geometry),
        onboarding=app.state.onboarding,
        report_writing=build_report_writing(settings, text_model=text_model),
    )
    editor = FakeImageEditor()
    sleeps: list[float] = []
    images = build_image_generation(
        settings,
        clock=frozen_clock,
        session_factory=session_factory,
        media=app.state.media,
        editor=editor,
        sleep=sleeps.append,
    )
    register_image_step(pipeline, images)
    app.state.images = images  # the API's manual retry uses the same fake
    worker = Worker(
        queue=app.state.job_queue,
        session_factory=session_factory,
        handlers={JOB_KIND: pipeline.handle},
        failure_hooks={JOB_KIND: pipeline.on_job_failed},
        worker_id="test-worker",
    )
    return ImageHarness(worker, pipeline, text_model, editor, images, sleeps)
