"""The PostgreSQL job queue (US1.7: AC1.7.1, AC1.7.2). Real PostgreSQL, rolled back per test."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.jobs.models import Job
from app.jobs.public import JobQueue
from app.jobs.service import MAX_REASON_LENGTH, WORKER_STOPPED_REASON
from app.platform.clock import FrozenClock

KIND = "test.kind"
KINDS = frozenset({KIND})


@pytest.fixture
def queue(frozen_clock: FrozenClock) -> JobQueue:
    return JobQueue(clock=frozen_clock, max_attempts=3, stale_after_seconds=60)


def test_an_enqueued_job_can_be_read_by_id_with_its_status_and_step(
    queue: JobQueue, db_session: Session
) -> None:
    job_id = queue.enqueue(db_session, KIND, {"runId": "r1"})
    db_session.commit()

    view = queue.get(db_session, job_id)
    assert view is not None
    assert (view.status, view.current_step, view.attempts) == ("queued", None, 0)
    assert queue.get(db_session, uuid.uuid4()) is None


def test_claiming_takes_the_oldest_job_of_the_wanted_kind_and_counts_the_attempt(
    queue: JobQueue, db_session: Session, frozen_clock: FrozenClock
) -> None:
    other = queue.enqueue(db_session, "other.kind", {})
    first = queue.enqueue(db_session, KIND, {"n": 1})
    frozen_clock.advance(seconds=1)
    queue.enqueue(db_session, KIND, {"n": 2})
    db_session.commit()

    claimed = queue.claim_next(db_session, "worker-a", KINDS)

    assert claimed is not None
    assert (claimed.id, claimed.payload, claimed.attempts) == (first, {"n": 1}, 1)
    running = queue.get(db_session, first)
    assert running is not None
    assert running.status == "running"
    untouched = queue.get(db_session, other)
    assert untouched is not None
    assert untouched.status == "queued"


def test_claiming_with_nothing_queued_returns_none(queue: JobQueue, db_session: Session) -> None:
    assert queue.claim_next(db_session, "worker-a", KINDS) is None


def test_progress_result_and_failure_are_recorded(
    queue: JobQueue, db_session: Session, frozen_clock: FrozenClock
) -> None:
    done_id = queue.enqueue(db_session, KIND, {})
    frozen_clock.advance(seconds=1)
    failed_id = queue.enqueue(db_session, KIND, {})
    db_session.commit()

    queue.heartbeat(db_session, done_id)  # not running yet: no effect
    claimed = queue.claim_next(db_session, "worker-a", KINDS)
    assert claimed is not None
    assert claimed.id == done_id
    queue.heartbeat(db_session, done_id, "measuring")
    step = queue.get(db_session, done_id)
    assert step is not None
    assert step.current_step == "measuring"
    queue.complete(db_session, done_id, {"ok": True})

    queue.fail(db_session, failed_id, "x" * (MAX_REASON_LENGTH + 50))

    finished = queue.get(db_session, done_id)
    assert finished is not None
    assert (finished.status, finished.result) == ("completed", {"ok": True})
    broken = queue.get(db_session, failed_id)
    assert broken is not None
    assert broken.status == "failed"
    assert broken.failure_reason is not None
    assert len(broken.failure_reason) == MAX_REASON_LENGTH


def test_a_job_whose_worker_died_is_queued_again_while_attempts_remain(
    queue: JobQueue, db_session: Session, frozen_clock: FrozenClock
) -> None:
    job_id = queue.enqueue(db_session, KIND, {})
    db_session.commit()
    queue.claim_next(db_session, "worker-a", KINDS)

    frozen_clock.advance(seconds=30)
    assert queue.recover_stale(db_session).resumed == ()  # heartbeat still fresh

    frozen_clock.advance(seconds=31)
    recovery = queue.recover_stale(db_session)

    assert [view.id for view in recovery.resumed] == [job_id]
    assert recovery.failed == ()
    again = queue.claim_next(db_session, "worker-b", KINDS)
    assert again is not None
    assert (again.id, again.attempts) == (job_id, 2)


def test_a_job_that_keeps_losing_its_worker_ends_failed_with_a_reason_never_running(
    queue: JobQueue, db_session: Session, frozen_clock: FrozenClock
) -> None:
    job_id = queue.enqueue(db_session, KIND, {})
    db_session.commit()
    for _ in range(queue.max_attempts):
        assert queue.claim_next(db_session, "worker-a", KINDS) is not None
        frozen_clock.advance(seconds=61)
        queue.recover_stale(db_session)

    view = queue.get(db_session, job_id)
    assert view is not None
    assert (view.status, view.failure_reason) == ("failed", WORKER_STOPPED_REASON)
    assert queue.claim_next(db_session, "worker-b", KINDS) is None


@pytest.fixture
def cleanup(committed_session_factory: Callable[[], Session]) -> Iterator[list[uuid.UUID]]:
    ids: list[uuid.UUID] = []
    yield ids
    with committed_session_factory() as session:
        session.execute(delete(Job).where(Job.id.in_(ids)))
        session.commit()


def test_two_workers_never_take_the_same_job(
    queue: JobQueue,
    committed_session_factory: Callable[[], Session],
    cleanup: list[uuid.UUID],
) -> None:
    """``FOR UPDATE SKIP LOCKED``: a job another transaction holds is passed over."""
    with committed_session_factory() as session:
        first = queue.enqueue(session, KIND, {"n": 1})
        second = queue.enqueue(session, KIND, {"n": 2})
        session.commit()
    cleanup.extend([first, second])

    holder = committed_session_factory()
    try:
        held = holder.scalars(
            select(Job).where(Job.id == first).with_for_update()
        ).one()  # worker A is busy claiming the oldest job
        assert held.id == first
        with committed_session_factory() as other:
            claimed = queue.claim_next(other, "worker-b", KINDS)
        assert claimed is not None
        assert claimed.id == second
    finally:
        holder.rollback()
        holder.close()


def test_queue_timestamps_follow_the_clock(
    queue: JobQueue, db_session: Session, frozen_clock: FrozenClock
) -> None:
    job_id = queue.enqueue(db_session, KIND, {})
    db_session.commit()
    created = db_session.get(Job, job_id)
    assert created is not None
    assert created.created_at == frozen_clock.now()
    frozen_clock.advance(timedelta(seconds=5))
    queue.claim_next(db_session, "worker-a", KINDS)
    claimed = db_session.get(Job, job_id)
    assert claimed is not None
    assert claimed.heartbeat_at == frozen_clock.now()
