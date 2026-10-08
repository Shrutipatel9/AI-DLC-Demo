"""Smaller U6 checks: the lost start race, the latency budget, the worker's wiring, the
onboarding tone port and the MediaStore reference check."""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import worker as worker_module
from app.ai.fakes import FakeImageEditor, load_latency_profile
from app.ai.ports import ImageInput
from app.ai.public import build_image_editor, build_text_model
from app.analysis import repositories
from app.analysis.pipeline import AnalysisPipeline, RunContext, StepResult
from app.analysis.steps import SLOT_COUNT
from app.jobs.public import JobContext, JobFailure
from app.measurement.public import FEATURE_KEYS
from app.media.models import MediaFile
from app.media.public import MediaStore
from app.onboarding.public import needs_reassurance
from app.platform.clock import FrozenClock
from app.report_writing.public import AnswerForAi, build_report_writing, fake_report
from tests.analysis.conftest import Harness, start
from tests.factories import SignedInUser
from tests.helpers import make_settings

PHOTO = ImageInput(b"photo", "image/png", "front")


def test_a_start_that_loses_the_race_returns_the_winners_run(
    client: TestClient,
    app: FastAPI,
    paid: SignedInUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7.1.3: the unique payment id decides; the loser returns the winner's run."""
    winner = start(client, paid).json()
    real = repositories.find_run_for_payment
    calls = {"n": 0}

    def blind_once(session: Session, payment_id: uuid.UUID) -> Any:
        calls["n"] += 1
        return None if calls["n"] == 1 else real(session, payment_id)

    monkeypatch.setattr("app.analysis.services.repositories.find_run_for_payment", blind_once)

    view = app.state.analysis.start(db_session, uuid.UUID(paid.user_id))

    assert str(view.run_id) == winner["runId"]
    assert calls["n"] == 2


class VirtualClock:
    """Sleep that advances a virtual stopwatch instead of waiting."""

    def __init__(self) -> None:
        self.elapsed = 0.0

    def sleep(self, seconds: float) -> None:
        self.elapsed += seconds


def test_the_realistic_profile_writes_all_text_and_covers_24_images_within_ten_minutes() -> None:
    """AC7.2.5: narratives and the 24 image slots fit NFR4's 10 minutes on the committed profile.

    U6 owns the text step and the 24 slots; U7 generates the images, so the images are
    scheduled here with the configured concurrency on the same profile.
    """
    settings = make_settings(AI_FAKE_PROFILE="realistic")
    stopwatch = VirtualClock()
    text_model = build_text_model(settings, responder=fake_report, sleep=stopwatch.sleep)
    writing = build_report_writing(settings, text_model=text_model, sleep=stopwatch.sleep)
    features = {key: {"measured": False, "values": {}} for key in FEATURE_KEYS}
    writing.write(
        answers=[AnswerForAi("Q", "A")],
        measurements={"features": features, "assessments": {}},
        photos=[PHOTO],
        reassure=False,
    )
    text_seconds = stopwatch.elapsed
    assert text_seconds == load_latency_profile().text_seconds

    image_clock = VirtualClock()
    editor = build_image_editor(settings, sleep=image_clock.sleep)
    assert isinstance(editor, FakeImageEditor)
    for _ in range(SLOT_COUNT):
        editor.edit(PHOTO, "x", "high")
    batches = math.ceil(SLOT_COUNT / settings.ai_image_concurrency)
    images_seconds = image_clock.elapsed / SLOT_COUNT * batches

    assert SLOT_COUNT == 24
    assert text_seconds + images_seconds <= 10 * 60


def test_the_pipeline_only_accepts_the_named_steps_and_runs_them_in_order(
    session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    pipeline = AnalysisPipeline(session_factory=session_factory, clock=frozen_clock)
    with pytest.raises(ValueError, match="unknown analysis step"):
        pipeline.register_step("polishing", 5, lambda _c: StepResult("done"))
    pipeline.register_step("assembling", 40, lambda _c: StepResult("done"))
    pipeline.register_step("measuring", 10, lambda _c: StepResult("done"))
    assert pipeline.registered_steps() == ["measuring", "assembling"]


def test_a_job_for_a_missing_run_fails_without_touching_anything(
    harness: Harness,
) -> None:
    context = JobContext(uuid.uuid4(), {"runId": str(uuid.uuid4())}, 1, lambda _step: None)
    with pytest.raises(JobFailure, match="not available"):
        harness.pipeline.handle(context)


def test_a_step_may_be_replaced_so_u7_and_u8_can_register_their_providers(
    harness: Harness,
) -> None:
    seen: list[RunContext] = []

    def images(ctx: RunContext) -> StepResult:
        seen.append(ctx)
        return StepResult("done", output={"slots": 24})

    harness.pipeline.register_step("generating_images", 30, images)
    assert harness.pipeline.registered_steps() == STEP_ORDER


STEP_ORDER = ["measuring", "writing", "generating_images", "assembling"]


def test_the_tone_port_answers_yes_or_no_and_refuses_an_unknown_level(
    client: TestClient,
    app: FastAPI,
    make_paid_user: Callable[..., SignedInUser],
    db_session: Session,
) -> None:
    user = make_paid_user({"q20": ("extreme", None), "q21": ("rarely", None)})
    service = app.state.onboarding
    uid = uuid.UUID(user.user_id)

    def ask(distress_at: str, frequency_at: str) -> bool:
        return needs_reassurance(
            service, db_session, uid, distress_at=distress_at, frequency_at=frequency_at
        )

    assert ask("moderate", "constantly")  # distress "extreme" is at or above "moderate"
    assert ask("extreme", "constantly")
    assert ask("none", "rarely") is not False  # both at their lowest level count as "at or above"
    with pytest.raises(ValueError, match="not an answer option"):
        ask("sky-high", "constantly")
    # No submitted questionnaire (an unknown user): never reassure.
    assert not needs_reassurance(
        service, db_session, uuid.uuid4(), distress_at="minor", frequency_at="rarely"
    )


def test_a_retired_file_that_something_still_references_is_kept(
    app: FastAPI, client: TestClient, paid: SignedInUser, db_session: Session
) -> None:
    media: MediaStore = app.state.media
    files = list(
        db_session.scalars(
            select(MediaFile).where(MediaFile.owner_user_id == uuid.UUID(paid.user_id))
        )
    )
    target = files[0]
    media.add_reference_check(lambda _session, file_id: file_id == target.id)

    assert media.retire(db_session, target.id) is None  # referenced: kept
    assert db_session.get(MediaFile, target.id) is not None
    spare = MediaFile(
        id=uuid.uuid4(),
        owner_user_id=target.owner_user_id,
        kind="photo",
        content_type="image/png",
        storage_key=f"{target.owner_user_id}/spare.png",
        size_bytes=1,
        created_at=target.created_at,
    )
    db_session.add(spare)
    db_session.flush()
    assert media.retire(db_session, spare.id) == spare.storage_key  # not referenced: removed
    assert media.retire(db_session, uuid.uuid4()) is None  # unknown: nothing to do


def test_the_worker_is_wired_from_settings_with_the_fakes_in_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = worker_module.build_worker(make_settings(FACE_LANDMARK_OVERRIDES_FILE=None))
    assert set(built.handlers) == {"analysis.run"}
    assert set(built.failure_hooks) == {"analysis.run"}
    assert built.heartbeat_seconds == 10.0


def test_the_worker_entry_point_refuses_bad_settings_and_stops_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.platform.settings import SettingsError

    def broken() -> Any:
        raise SettingsError("Invalid configuration: OPENAI_API_KEY: required")

    monkeypatch.setattr(worker_module, "get_settings", broken)
    assert worker_module.main([]) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err

    settings = make_settings()
    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)

    class QuickWorker:
        def run_forever(self, stop: Any) -> None:
            stop.set()

    monkeypatch.setattr(worker_module, "build_worker", lambda _settings: QuickWorker())
    assert worker_module.main(["--label", "test"]) == 0
