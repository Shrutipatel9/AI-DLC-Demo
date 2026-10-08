"""The worker loop (US1.7: AC1.7.1, AC1.7.2, AC1.7.3)."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.jobs.models import Job
from app.jobs.public import JobContext, JobFailure, JobQueue, JobView, Worker
from app.platform.clock import FrozenClock

KIND = "test.kind"
CANARY = "CANARY-ANSWER-TEXT-7f3a"


@pytest.fixture
def queue(frozen_clock: FrozenClock) -> JobQueue:
    return JobQueue(clock=frozen_clock, max_attempts=2, stale_after_seconds=60)


def make_worker(
    queue: JobQueue,
    factory: Callable[[], Session],
    handler: Callable[[JobContext], dict[str, Any] | None],
    hook: Callable[[JobView], None] | None = None,
    **kwargs: Any,
) -> Worker:
    return Worker(
        queue=queue,
        session_factory=factory,
        handlers={KIND: handler},
        failure_hooks={KIND: hook} if hook else None,
        worker_id="test-worker",
        **kwargs,
    )


def state(queue: JobQueue, factory: Callable[[], Session], job_id: uuid.UUID) -> JobView:
    with factory() as session:
        view = queue.get(session, job_id)
    assert view is not None
    return view


def test_the_worker_runs_a_job_outside_the_request_and_records_step_and_result(
    queue: JobQueue, session_factory: Callable[[], Session]
) -> None:
    seen: list[str | None] = []

    def handler(job: JobContext) -> dict[str, Any]:
        job.set_step("measuring")
        seen.append(state(queue, session_factory, job.job_id).current_step)
        return {"done": True}

    with session_factory() as session:
        job_id = queue.enqueue(session, KIND, {"runId": "r"})  # the "web request" returns here
        session.commit()
    assert state(queue, session_factory, job_id).status == "queued"

    worker = make_worker(queue, session_factory, handler)
    assert worker.run_once() is True

    assert seen == ["measuring"]  # the step is readable by id while the job runs
    final = state(queue, session_factory, job_id)
    assert (final.status, final.result) == ("completed", {"done": True})
    assert worker.run_once() is False  # nothing left


def test_a_failure_is_recorded_with_its_reason_and_reported_to_the_owner(
    queue: JobQueue, session_factory: Callable[[], Session]
) -> None:
    reported: list[JobView] = []

    def handler(_job: JobContext) -> None:
        raise JobFailure("The report text could not be written.")

    with session_factory() as session:
        job_id = queue.enqueue(session, KIND, {})
        session.commit()
    make_worker(queue, session_factory, handler, reported.append).run_once()

    view = state(queue, session_factory, job_id)
    assert (view.status, view.failure_reason) == ("failed", "The report text could not be written.")
    assert [job.id for job in reported] == [job_id]


def test_an_unexpected_error_fails_the_job_and_logs_no_message_or_answer_text(
    queue: JobQueue,
    session_factory: Callable[[], Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC1.7.3: the failure is recorded and logged without photo data or answer text."""

    def handler(_job: JobContext) -> None:
        raise RuntimeError(f"the answer was {CANARY}")

    with session_factory() as session:
        job_id = queue.enqueue(session, KIND, {})
        session.commit()
    with caplog.at_level(logging.DEBUG):
        make_worker(queue, session_factory, handler).run_once()

    view = state(queue, session_factory, job_id)
    assert view.status == "failed"
    assert view.failure_reason == "The job stopped unexpectedly."
    assert CANARY not in view.failure_reason
    logged = " ".join(
        f"{record.getMessage()} {record.__dict__.get('errorClass', '')} {record.exc_text or ''}"
        for record in caplog.records
    )
    assert CANARY not in logged
    assert "RuntimeError" in logged


def test_a_job_left_running_by_a_dead_worker_is_resumed_and_completed(
    queue: JobQueue, session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    """AC1.7.2: after a restart the job ends completed, never running forever."""
    attempts: list[int] = []

    def handler(job: JobContext) -> dict[str, Any]:
        attempts.append(job.attempt)
        return {"attempt": job.attempt}

    with session_factory() as session:
        job_id = queue.enqueue(session, KIND, {})
        session.commit()
        queue.claim_next(session, "dead-worker", frozenset({KIND}))  # then the process died
    frozen_clock.advance(seconds=120)

    make_worker(queue, session_factory, handler).run_once()

    assert attempts == [2]
    assert state(queue, session_factory, job_id).status == "completed"


def test_a_job_that_cannot_be_resumed_ends_failed_and_the_owner_is_told(
    queue: JobQueue, session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    reported: list[JobView] = []
    with session_factory() as session:
        job_id = queue.enqueue(session, KIND, {})
        session.commit()
        for attempt in range(queue.max_attempts):
            queue.claim_next(session, "dead-worker", frozenset({KIND}))
            frozen_clock.advance(seconds=120)
            if attempt == 0:
                queue.recover_stale(session)  # the second worker died too; the worker finds it

    make_worker(queue, session_factory, lambda _j: None, reported.append).run_once()

    assert state(queue, session_factory, job_id).status == "failed"
    assert [job.id for job in reported] == [job_id]


def test_a_failing_failure_hook_does_not_stop_the_worker(
    queue: JobQueue, session_factory: Callable[[], Session]
) -> None:
    def hook(_job: JobView) -> None:
        raise RuntimeError("hook broke")

    def handler(_job: JobContext) -> None:
        raise JobFailure("boom")

    with session_factory() as session:
        job_id = queue.enqueue(session, KIND, {})
        session.commit()
    make_worker(queue, session_factory, handler, hook).run_once()
    assert state(queue, session_factory, job_id).status == "failed"


def test_run_forever_polls_until_stopped(
    queue: JobQueue, session_factory: Callable[[], Session]
) -> None:
    stop = threading.Event()

    def handler(_job: JobContext) -> None:
        stop.set()

    with session_factory() as session:
        queue.enqueue(session, KIND, {})
        session.commit()
    make_worker(queue, session_factory, handler, poll_interval_seconds=0.01).run_forever(stop)
    assert stop.is_set()


def test_the_worker_keeps_polling_after_a_loop_error(
    queue: JobQueue, session_factory: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = threading.Event()
    calls = {"n": 0}
    worker = make_worker(queue, session_factory, lambda _j: None, poll_interval_seconds=0.01)

    def flaky() -> bool:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database blip")
        stop.set()
        return False

    monkeypatch.setattr(worker, "run_once", flaky)
    worker.run_forever(stop)
    assert calls["n"] == 2


@pytest.fixture
def cleanup(committed_session_factory: Callable[[], Session]) -> Iterator[list[uuid.UUID]]:
    ids: list[uuid.UUID] = []
    yield ids
    with committed_session_factory() as session:
        session.execute(delete(Job).where(Job.id.in_(ids)))
        session.commit()


def test_a_long_job_keeps_its_heartbeat_fresh(
    queue: JobQueue,
    committed_session_factory: Callable[[], Session],
    cleanup: list[uuid.UUID],
) -> None:
    beats: list[uuid.UUID] = []
    real_heartbeat = queue.heartbeat

    def counting(session: Session, job_id: uuid.UUID, step: str | None = None) -> None:
        beats.append(job_id)
        real_heartbeat(session, job_id, step)

    queue.heartbeat = counting  # type: ignore[method-assign]

    def handler(_job: JobContext) -> None:
        time.sleep(0.3)  # a slow vendor call

    with committed_session_factory() as session:
        cleanup.append(queue.enqueue(session, KIND, {}))
        session.commit()
    make_worker(queue, committed_session_factory, handler, heartbeat_seconds=0.05).run_once()
    assert len(beats) >= 2
