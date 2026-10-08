"""Analysis fixtures: the real app on real PostgreSQL (rolled back), users who submitted the
questionnaire, uploaded three same-person photos (real MediaPipe) and paid (a succeeded payment
row), a worker draining jobs in-process with the AI text FAKE (never OpenAI)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fakes import FakeTextModel
from app.analysis.public import JOB_KIND, AnalysisPipeline, build_pipeline
from app.jobs.public import Worker
from app.measurement.public import build_measurement
from app.onboarding.definition import QuestionnaireDefinition
from app.payments.models import PaymentStatus
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.report_writing.public import build_report_writing, fake_report
from tests.factories import SignedInUser, verified_user
from tests.identity.conftest import bearer
from tests.onboarding.conftest import answer_all, give_consent, submit
from tests.payments.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    app,
    client,
    consistent,
    email_fake,
    fake_gateway,
    insert_payment,
    media_root,
    seed_definition,
    settings_overrides,
    submitted,
    upload_consistent_set,
    webhooks,
)


@pytest.fixture
def text_model() -> FakeTextModel:
    """The report-writing text fake: records calls, can fail or return malformed output."""
    return FakeTextModel(fake_report)


@dataclass
class Harness:
    """An in-process worker with the real pipeline, wired like ``app.worker``."""

    worker: Worker
    pipeline: AnalysisPipeline
    text_model: FakeTextModel

    def drain(self, limit: int = 10) -> int:
        """Run queued jobs until none is left; returns how many ran."""
        ran = 0
        while ran < limit and self.worker.run_once():
            ran += 1
        return ran


@pytest.fixture
def harness(
    app: FastAPI,  # noqa: F811
    client: TestClient,  # noqa: F811  (starts the app so the face model is loaded)
    session_factory: Callable[[], Session],
    frozen_clock: FrozenClock,
    text_model: FakeTextModel,
) -> Harness:
    settings = app.state.settings
    pipeline = build_pipeline(
        settings,
        clock=frozen_clock,
        session_factory=session_factory,
        media=app.state.media,
        measurement=build_measurement(settings, geometry=app.state.face_geometry),
        onboarding=app.state.onboarding,
        report_writing=build_report_writing(settings, text_model=text_model),
    )
    worker = Worker(
        queue=app.state.job_queue,
        session_factory=session_factory,
        handlers={JOB_KIND: pipeline.handle},
        failure_hooks={JOB_KIND: pipeline.on_job_failed},
        worker_id="test-worker",
    )
    return Harness(worker, pipeline, text_model)


@pytest.fixture
def paid(
    consistent: SignedInUser,  # noqa: F811
    db_session: Session,
    frozen_clock: FrozenClock,
) -> SignedInUser:
    """A user with three consistent photos and a succeeded payment (no analysis yet)."""
    insert_payment(
        db_session, consistent.user_id, now=frozen_clock.now(), status=PaymentStatus.SUCCEEDED
    )
    return consistent


@pytest.fixture
def make_paid_user(
    client: TestClient,  # noqa: F811
    email_fake: RecordingEmailSender,  # noqa: F811
    seed_definition: QuestionnaireDefinition,  # noqa: F811
    db_session: Session,
    frozen_clock: FrozenClock,
) -> Callable[..., SignedInUser]:
    """Create a paid user with custom questionnaire answers (for the privacy tests)."""

    def make(overrides: dict[str, tuple[object, str | None]] | None = None) -> SignedInUser:
        user = verified_user(client, email_fake)
        give_consent(client, user)
        answer_all(client, user, seed_definition, overrides=overrides)
        assert submit(client, user).status_code == 200
        upload_consistent_set(client, user)
        insert_payment(
            db_session, user.user_id, now=frozen_clock.now(), status=PaymentStatus.SUCCEEDED
        )
        return user

    return make


def start(client: TestClient, user: SignedInUser) -> Any:  # noqa: F811
    """``POST /analysis/runs`` as the web app does."""
    return client.post("/analysis/runs", headers=bearer(user.access_token))


def current(client: TestClient, user: SignedInUser) -> Any:  # noqa: F811
    """``GET /analysis/runs/current``."""
    return client.get("/analysis/runs/current", headers=bearer(user.access_token))


def rerun(client: TestClient, user: SignedInUser) -> Any:  # noqa: F811
    """``POST /analysis/runs/current/rerun``."""
    return client.post("/analysis/runs/current/rerun", headers=bearer(user.access_token))


def step_states(body: dict[str, Any]) -> dict[str, str]:
    """``{step key: state}`` of a run body."""
    return {step["key"]: step["state"] for step in body["steps"]}


def as_uuid(value: str) -> uuid.UUID:
    """A user id from the factories (a string) as a UUID."""
    return uuid.UUID(value)
