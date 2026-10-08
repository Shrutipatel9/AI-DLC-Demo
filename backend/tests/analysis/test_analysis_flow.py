"""The analysis flow through the real API, worker and pipeline (US7.1, US7.2, US7.6, US7.9,
US7.11, US1.7): payment first, one run per payment, resume, re-run, privacy and logs.

The AI text vendor is the recording FAKE; no paid service is ever called (NFR-008).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.errors import AiUnavailableError
from app.analysis.models import (
    AnalysisImageSlot,
    AnalysisResult,
    AnalysisRun,
    AnalysisRunPhoto,
    AnalysisStep,
)
from app.analysis.pipeline import RunContext, StepResult
from app.jobs.models import Job
from app.measurement.public import FEATURE_KEYS
from app.media.models import MediaFile
from app.payments.models import PaymentStatus
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.report_writing.public import REASSURANCE_INSTRUCTION
from tests.analysis.conftest import (
    Harness,
    as_uuid,
    current,
    rerun,
    start,
    step_states,
)
from tests.faces import A_FRONT, B_LEFT
from tests.factories import SignedInUser, verified_user
from tests.payments.conftest import insert_payment
from tests.photos.conftest import upload

STEPS = ["measuring", "writing", "generating_images", "assembling"]


def job_count(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Job)) or 0)


def run_row(session: Session, user: SignedInUser) -> AnalysisRun:
    return session.scalars(
        select(AnalysisRun).where(AnalysisRun.user_id == as_uuid(user.user_id))
    ).one()


# --- Start: payment first, then photos (AC7.1.1, AC7.1.2) -------------------------------------


def test_the_analysis_routes_need_a_signed_in_user(client: TestClient) -> None:
    for method, path in (
        ("POST", "/analysis/runs"),
        ("GET", "/analysis/runs/current"),
        ("POST", "/analysis/runs/current/rerun"),
    ):
        assert client.request(method, path).status_code == 401


def test_start_without_payment_is_402_even_when_the_photos_are_inconsistent(
    client: TestClient, consistent: SignedInUser, db_session: Session
) -> None:
    """AC6.4.2 precedence: payment first. No job and no vendor call (FR-015, BR-001)."""
    assert start(client, consistent).json()["error"]["code"] == "PAYMENT_REQUIRED"
    assert upload(client, consistent, "left_3q", B_LEFT).status_code == 200
    response = start(client, consistent)
    assert (response.status_code, response.json()["error"]["code"]) == (402, "PAYMENT_REQUIRED")
    assert job_count(db_session) == 0
    assert db_session.scalar(select(func.count()).select_from(AnalysisRun)) == 0


def test_a_pending_or_failed_payment_does_not_unlock_the_analysis(
    client: TestClient,
    consistent: SignedInUser,
    db_session: Session,
    frozen_clock: FrozenClock,
) -> None:
    for status in (PaymentStatus.PENDING, PaymentStatus.FAILED):
        insert_payment(db_session, consistent.user_id, now=frozen_clock.now(), status=status)
    assert start(client, consistent).status_code == 402


def test_start_after_paying_with_an_inconsistent_set_is_409_and_starts_nothing(
    client: TestClient, paid: SignedInUser, db_session: Session
) -> None:
    """AC7.1.2: the 409 message, and no run or job."""
    assert upload(client, paid, "left_3q", B_LEFT).status_code == 200

    response = start(client, paid)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PHOTO_IDENTITY_MISMATCH"
    assert job_count(db_session) == 0
    assert db_session.scalar(select(func.count()).select_from(AnalysisRun)) == 0


def test_start_with_an_incomplete_photo_set_is_409(
    client: TestClient,
    submitted: SignedInUser,
    db_session: Session,
    frozen_clock: FrozenClock,
) -> None:
    insert_payment(
        db_session, submitted.user_id, now=frozen_clock.now(), status=PaymentStatus.SUCCEEDED
    )
    response = start(client, submitted)
    assert (response.status_code, response.json()["error"]["code"]) == (
        409,
        "PHOTO_SET_INCOMPLETE",
    )


# --- The run end to end (AC7.1.1, AC7.6.1, AC7.9.3) ------------------------------------------


def test_start_returns_the_run_and_a_job_then_the_worker_completes_every_named_step(
    client: TestClient, paid: SignedInUser, harness: Harness, db_session: Session
) -> None:
    response = start(client, paid)

    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] == "running"
    assert step_states(body) == {
        "measuring": "current",
        "writing": "waiting",
        "generating_images": "waiting",
        "assembling": "waiting",
    }
    assert (body["rerunAvailable"], body["failureMessage"], body["contactSupport"]) == (
        False,
        None,
        False,
    )
    assert 1 <= body["expectedWaitMinutes"] <= 10
    assert job_count(db_session) == 1  # the job outlives the request (AC1.7.1)
    assert harness.text_model.calls == []  # nothing runs inside the request

    assert harness.drain() == 1

    done = current(client, paid).json()
    assert done["runId"] == body["runId"]
    assert done["status"] == "completed"
    assert step_states(done) == dict.fromkeys(STEPS, "done")
    job = db_session.scalars(select(Job)).one()
    assert (job.status, job.current_step, job.worker_id) == ("completed", "assembling", None)


def test_the_stored_result_has_all_eleven_features_and_twenty_four_image_slots(
    client: TestClient, paid: SignedInUser, harness: Harness, db_session: Session
) -> None:
    run_id = uuid.UUID(start(client, paid).json()["runId"])
    harness.drain()

    result = db_session.scalars(select(AnalysisResult)).one()  # one result for me (AC7.9.3)
    assert result.run_id == run_id
    assert str(result.user_id) == paid.user_id
    # JSONB does not keep key order: readers iterate FEATURE_KEYS.
    assert set(result.result["reportText"]["features"]) == set(FEATURE_KEYS)
    assert set(result.result["measurements"]["features"]) == set(FEATURE_KEYS)
    assert "symmetry" in result.result["measurements"]["assessments"]
    slots = db_session.scalars(select(AnalysisImageSlot)).all()
    assert len(slots) == 24
    assert {slot.status for slot in slots} == {"not_available_yet"}
    assert {slot.slot_kind for slot in slots} == {"feature_after", "hairstyle", "outfit", "aging"}
    steps = {s.key: s for s in db_session.scalars(select(AnalysisStep)).all()}
    assert all(step.status == "done" for step in steps.values())
    assert steps["measuring"].output is not None
    assert "measurements" in steps["measuring"].output


def test_one_run_per_payment_a_second_start_returns_it_and_a_finished_run_is_409(
    client: TestClient, paid: SignedInUser, harness: Harness, db_session: Session
) -> None:
    """AC7.1.3 (sequential), AC7.1.4, AC7.6.3."""
    first = start(client, paid).json()
    second = start(client, paid)
    assert (second.status_code, second.json()["runId"]) == (202, first["runId"])
    assert job_count(db_session) == 1

    harness.drain()
    calls = len(harness.text_model.calls)
    again = start(client, paid)

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ANALYSIS_ALREADY_COMPLETE"
    assert job_count(db_session) == 1
    assert harness.drain() == 0
    assert len(harness.text_model.calls) == calls == 1  # no second vendor call (NFR10)


def test_current_is_404_without_a_run_and_never_shows_another_users_run(
    client: TestClient,
    paid: SignedInUser,
    email_fake: RecordingEmailSender,
    harness: Harness,
) -> None:
    assert current(client, paid).status_code == 404
    start(client, paid)
    assert current(client, paid).status_code == 200
    # Not a stranger's run: another user who has never started sees no run (AC1.8.1).
    stranger = verified_user(client, email_fake)
    assert current(client, stranger).status_code == 404
    assert rerun(client, stranger).status_code == 404


# --- Privacy (AC7.4.1, AC7.4.2, AC7.4.3) ------------------------------------------------------


def test_the_ai_request_has_photos_measurements_and_non_medical_answers_only(
    client: TestClient,
    make_paid_user: Callable[..., SignedInUser],
    harness: Harness,
    seed_definition: Any,
) -> None:
    user = make_paid_user(
        {
            "q14": ("CANARY-LIKED-FEATURE-eyes", None),
            "q15": ("CANARY-DISLIKED-FEATURE-nose", None),
            "q22": ("CANARY-MOTIVATION-wedding", None),
            "q9": (True, "CANARY-MEDICATION-FOLLOWUP-aspirin"),
            "q11": (True, "CANARY-ALLERGY-FOLLOWUP-latex"),
        }
    )
    start(client, user)
    harness.drain()

    request = harness.text_model.calls[0]
    sent = " ".join(message.content for message in request.messages)
    for canary in (
        "CANARY-LIKED-FEATURE-eyes",
        "CANARY-DISLIKED-FEATURE-nose",
        "CANARY-MOTIVATION-wedding",
    ):
        assert canary in sent  # goal, motivation, liked and disliked answers are sent
    for question_id in ("q14", "q15", "q22", "q18"):
        assert seed_definition.question(question_id).text in sent  # with the real question text
    for medical in ("q8", "q9", "q10", "q11", "q12"):
        assert seed_definition.question(medical).text not in sent
    assert "CANARY-MEDICATION" not in sent
    assert "CANARY-ALLERGY" not in sent
    assert [label for label, _size in request.images] == ["front", "left_3q", "right_3q"]
    assert '"measurements"' in sent
    assert '"symmetry"' in sent


@pytest.mark.parametrize(
    ("overrides", "reassured"),
    [
        ({}, False),
        ({"q20": ("minor", None)}, False),
        ({"q20": ("moderate", None)}, True),
        ({"q20": ("extreme", None)}, True),
        ({"q21": ("occasionally", None)}, False),
        ({"q21": ("frequently", None)}, True),
        ({"q21": ("constantly", None)}, True),
    ],
)
def test_the_reassuring_tone_instruction_follows_the_configured_levels(
    client: TestClient,
    make_paid_user: Callable[..., SignedInUser],
    harness: Harness,
    overrides: dict[str, tuple[object, str | None]],
    reassured: bool,
) -> None:
    user = make_paid_user(overrides)
    start(client, user)
    harness.drain()
    system = harness.text_model.calls[0].messages[0].content
    assert (REASSURANCE_INSTRUCTION in system) is reassured


def test_logs_never_contain_answer_text_or_photo_bytes_through_a_whole_run_and_a_failure(
    client: TestClient,
    make_paid_user: Callable[..., SignedInUser],
    harness: Harness,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC1.7.3, AC1.8.3."""
    canary = "CANARY-ANSWER-TEXT-55aa"
    user = make_paid_user({"q14": (canary, None), "q9": (True, "CANARY-MEDS-77")})
    harness.text_model.fail_next(AiUnavailableError(f"vendor said {canary}"), times=3)
    with caplog.at_level(logging.DEBUG):
        start(client, user)
        harness.drain()  # the writing step fails after its attempts
        rerun(client, user)
        harness.drain()  # and the re-run completes
    assert current(client, user).json()["status"] == "completed"
    logged = " ".join(
        f"{r.getMessage()} {r.__dict__.get('errorClass', '')} {r.exc_text or ''}"
        for r in caplog.records
    )
    assert canary not in logged
    assert "CANARY-MEDS-77" not in logged
    assert "PNG" not in logged


# --- Failure, free re-run and resume (AC7.6.2, AC7.11.x) ----------------------------------------


def test_a_failed_run_explains_in_plain_language_and_offers_one_free_rerun_that_keeps_done_steps(
    client: TestClient, paid: SignedInUser, harness: Harness, db_session: Session
) -> None:
    harness.text_model.fail_next(AiUnavailableError("down"), times=3)  # every text attempt
    run_id = uuid.UUID(start(client, paid).json()["runId"])
    harness.drain()

    failed = current(client, paid).json()
    assert failed["status"] == "failed"
    assert step_states(failed) == {
        "measuring": "done",
        "writing": "failed",
        "generating_images": "waiting",
        "assembling": "waiting",
    }
    assert failed["rerunAvailable"] is True
    assert failed["contactSupport"] is False
    assert "went wrong on our side" in failed["failureMessage"]
    assert "payment still covers" in failed["failureMessage"]
    assert "AiUnavailableError" not in failed["failureMessage"]  # never a raw error
    assert (
        db_session.scalar(select(func.count()).select_from(AnalysisResult)) == 0
    )  # nothing half-valid
    measured_at = db_session.get(AnalysisStep, (run_id, "measuring")).completed_at  # type: ignore[union-attr]

    response = rerun(client, paid)
    assert response.status_code == 202
    assert response.json()["status"] == "running"
    harness.drain()

    done = current(client, paid).json()
    assert (done["status"], done["rerunAvailable"]) == ("completed", False)
    assert db_session.get(AnalysisStep, (run_id, "measuring")).completed_at == measured_at  # type: ignore[union-attr]
    assert len(harness.text_model.calls) == 4  # three failures, one success
    assert rerun(client, paid).json()["error"]["code"] == "RERUN_NOT_AVAILABLE"


def test_when_the_free_rerun_also_fails_the_user_is_told_to_contact_support(
    client: TestClient, paid: SignedInUser, harness: Harness
) -> None:
    """AC7.11.3."""
    harness.text_model.fail_next(AiUnavailableError("down"), times=6)
    start(client, paid)
    harness.drain()
    assert rerun(client, paid).status_code == 202
    harness.drain()

    final = current(client, paid).json()
    assert final["status"] == "failed"
    assert final["rerunAvailable"] is False
    assert final["contactSupport"] is True
    assert "contact support" in final["failureMessage"].lower()
    response = rerun(client, paid)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "RERUN_NOT_AVAILABLE")
    again = start(client, paid)  # a failed run is not "complete": it returns the same failed run
    assert again.json()["status"] == "failed"


def test_rerun_needs_a_failed_run(client: TestClient, paid: SignedInUser, harness: Harness) -> None:
    assert rerun(client, paid).status_code == 404  # no run yet
    start(client, paid)
    assert rerun(client, paid).json()["error"]["code"] == "RERUN_NOT_AVAILABLE"  # still running
    harness.drain()
    assert rerun(client, paid).json()["error"]["code"] == "RERUN_NOT_AVAILABLE"  # completed


def test_a_job_resumed_after_a_restart_does_not_repeat_a_completed_step(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    frozen_clock: FrozenClock,
    db_session: Session,
) -> None:
    """AC7.6.2 and AC1.7.2: the process dies mid-run; the next worker resumes it."""
    measured: list[uuid.UUID] = []
    real_measuring = harness.pipeline._steps["measuring"][1]

    def counting(ctx: RunContext) -> StepResult:
        measured.append(ctx.run_id)
        return real_measuring(ctx)

    def dies(_ctx: RunContext) -> StepResult:
        raise SystemExit  # the process is killed during the writing step

    harness.pipeline.register_step("measuring", 10, counting)
    real_writing = harness.pipeline._steps["writing"][1]
    harness.pipeline.register_step("writing", 20, dies)
    start(client, paid)
    with pytest.raises(SystemExit):
        harness.worker.run_once()
    assert measured
    assert db_session.scalars(select(Job)).one().status == "running"

    frozen_clock.advance(timedelta(minutes=5))
    harness.pipeline.register_step("writing", 20, real_writing)
    harness.drain()

    assert len(measured) == 1  # the saved measurements were used, not recomputed
    assert len(harness.text_model.calls) == 1
    assert current(client, paid).json()["status"] == "completed"
    db_session.expire_all()
    assert db_session.scalars(select(Job)).one().attempts == 2


def test_a_run_whose_worker_never_comes_back_ends_failed_not_running_forever(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    frozen_clock: FrozenClock,
    db_session: Session,
) -> None:
    """AC1.7.2: after the last attempt the job and the run fail, and the free re-run works."""
    start(client, paid)
    job = db_session.scalars(select(Job)).one()
    job.status, job.attempts, job.current_step = "running", 3, "writing"
    job.heartbeat_at = frozen_clock.now()
    db_session.commit()
    frozen_clock.advance(timedelta(minutes=5))

    harness.worker.run_once()

    body = current(client, paid).json()
    assert body["status"] == "failed"
    assert body["rerunAvailable"] is True
    assert step_states(body)["writing"] == "failed"
    db_session.expire_all()
    assert db_session.scalars(select(Job)).one().status == "failed"


# --- Photos recorded at start (R-02) and step failures -----------------------------------------


def test_the_run_keeps_using_the_photos_it_started_with_after_a_retake(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    db_session: Session,
    app: Any,
) -> None:
    """R-02: a retake never deletes the file a run needs, and the run uses the snapshot."""
    run_id = uuid.UUID(start(client, paid).json()["runId"])
    snapshot = {
        row.angle: row.media_file_id
        for row in db_session.scalars(
            select(AnalysisRunPhoto).where(AnalysisRunPhoto.run_id == run_id)
        )
    }
    assert set(snapshot) == {"front", "left_3q", "right_3q"}

    assert upload(client, paid, "front", A_FRONT).status_code == 200  # a retake

    assert db_session.get(MediaFile, snapshot["front"]) is not None  # kept, not deleted
    harness.drain()
    assert current(client, paid).json()["status"] == "completed"
    now_front = db_session.scalars(
        select(MediaFile.id).where(MediaFile.owner_user_id == as_uuid(paid.user_id))
    ).all()
    assert snapshot["front"] in now_front


def test_an_unreadable_snapshot_photo_fails_the_measuring_step(
    client: TestClient, paid: SignedInUser, harness: Harness, db_session: Session, app: Any
) -> None:
    run_id = uuid.UUID(start(client, paid).json()["runId"])
    front = db_session.get(AnalysisRunPhoto, (run_id, "front"))
    assert front is not None
    record = db_session.get(MediaFile, front.media_file_id)
    assert record is not None
    app.state.media.storage.delete(record.storage_key)  # the bytes are gone

    harness.drain()

    body = current(client, paid).json()
    assert step_states(body)["measuring"] == "failed"
    assert body["rerunAvailable"] is True


def test_an_unexpected_step_error_fails_the_run_with_a_generic_reason(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(_ctx: RunContext) -> StepResult:
        raise RuntimeError("secret detail CANARY-STEP-ERROR")

    harness.pipeline.register_step("writing", 20, broken)
    start(client, paid)
    with caplog.at_level(logging.DEBUG):
        harness.drain()

    run = db_session.scalars(select(AnalysisRun)).one()
    assert (run.status, run.failed_step, run.failure_count) == ("failed", "writing", 1)
    assert "CANARY" not in (run.failure_reason or "")
    assert "CANARY" not in " ".join(r.getMessage() for r in caplog.records)
    assert "failed" in step_states(current(client, paid).json()).values()
