"""The job queue (US1.7): enqueue, claim, heartbeat, finish and recover.

Every method that takes a ``session`` and changes data commits it itself, except
:meth:`JobQueue.enqueue`, which only stages the row so the caller's transaction (for example
"create the analysis run and its job") commits both or neither.

Claiming uses ``SELECT ... FOR UPDATE SKIP LOCKED``: two workers never take the same job
(AC1.7.1). A job whose worker died is found by its stale heartbeat: it is queued again
(resumed) while it has attempts left, otherwise it ends ``failed`` with a reason, so a job is
never ``running`` forever (AC1.7.2).

Reasons are short, plain text written by our own code. They never carry photo data, answer
text or vendor bodies (AC1.7.3).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.jobs.models import Job, JobStatus
from app.platform.clock import Clock

logger = logging.getLogger("jobs")

MAX_REASON_LENGTH = 500
WORKER_STOPPED_REASON = "The background worker stopped before this job finished."


@dataclass(frozen=True)
class JobView:
    """A job's state as read by id."""

    id: uuid.UUID
    kind: str
    status: str
    current_step: str | None
    result: dict[str, Any] | None
    failure_reason: str | None
    attempts: int


@dataclass(frozen=True)
class ClaimedJob:
    """A job a worker has just taken."""

    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    attempts: int


@dataclass(frozen=True)
class Recovery:
    """What :meth:`JobQueue.recover_stale` did."""

    resumed: tuple[JobView, ...]
    failed: tuple[JobView, ...]


def _view(job: Job) -> JobView:
    return JobView(
        id=job.id,
        kind=job.kind,
        status=job.status,
        current_step=job.current_step,
        result=job.result,
        failure_reason=job.failure_reason,
        attempts=job.attempts,
    )


class JobQueue:
    """The PostgreSQL-backed queue.

    Args:
        clock: Time source.
        max_attempts: How often a job may be started (a resume after a dead worker counts).
        stale_after_seconds: A running job with an older heartbeat belongs to a dead worker.
    """

    def __init__(self, *, clock: Clock, max_attempts: int, stale_after_seconds: float) -> None:
        self.clock = clock
        self.max_attempts = max_attempts
        self.stale_after_seconds = stale_after_seconds

    def enqueue(self, session: Session, kind: str, payload: dict[str, Any]) -> uuid.UUID:
        """Stage a ``queued`` job; the caller commits (the web request then returns).

        ``payload`` must hold ids only.
        """
        now = self.clock.now()
        job = Job(
            id=uuid.uuid4(),
            kind=kind,
            payload=payload,
            status=JobStatus.QUEUED.value,
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.flush()
        return job.id

    def get(self, session: Session, job_id: uuid.UUID) -> JobView | None:
        """The job's status and current step by id (AC1.7.1)."""
        job = session.get(Job, job_id)
        return None if job is None else _view(job)

    def claim_next(
        self, session: Session, worker_id: str, kinds: frozenset[str]
    ) -> ClaimedJob | None:
        """Take the oldest queued job of ``kinds`` (``SKIP LOCKED``); commits."""
        job = session.scalars(
            select(Job)
            .where(Job.status == JobStatus.QUEUED.value, Job.kind.in_(sorted(kinds)))
            .order_by(Job.created_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).one_or_none()
        if job is None:
            session.rollback()
            return None
        now = self.clock.now()
        job.status = JobStatus.RUNNING.value
        job.attempts += 1
        job.worker_id = worker_id
        job.heartbeat_at = now
        job.updated_at = now
        claimed = ClaimedJob(job.id, job.kind, dict(job.payload), job.attempts)
        session.commit()
        return claimed

    def heartbeat(self, session: Session, job_id: uuid.UUID, step: str | None = None) -> None:
        """Show the worker is alive, optionally recording the step it is on; commits."""
        now = self.clock.now()
        values: dict[str, Any] = {"heartbeat_at": now, "updated_at": now}
        if step is not None:
            values["current_step"] = step
        session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.RUNNING.value)
            .values(**values)
        )
        session.commit()

    def complete(
        self, session: Session, job_id: uuid.UUID, result: dict[str, Any] | None = None
    ) -> None:
        """End the job ``completed`` with a small result; commits."""
        self._finish(session, job_id, JobStatus.COMPLETED, result=result, reason=None)

    def fail(self, session: Session, job_id: uuid.UUID, reason: str) -> None:
        """End the job ``failed`` with a reason; commits."""
        self._finish(session, job_id, JobStatus.FAILED, result=None, reason=reason)

    def _finish(
        self,
        session: Session,
        job_id: uuid.UUID,
        status: JobStatus,
        *,
        result: dict[str, Any] | None,
        reason: str | None,
    ) -> None:
        now = self.clock.now()
        session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=status.value,
                result=result,
                failure_reason=None if reason is None else reason[:MAX_REASON_LENGTH],
                finished_at=now,
                updated_at=now,
                worker_id=None,
            )
        )
        session.commit()

    def recover_stale(self, session: Session) -> Recovery:
        """Resume or fail jobs whose worker died (AC1.7.2); commits.

        A running job with a stale heartbeat is queued again while it has attempts left;
        otherwise it ends ``failed`` with a reason.
        """
        cutoff = self.clock.now() - timedelta(seconds=self.stale_after_seconds)
        stale = session.scalars(
            select(Job)
            .where(Job.status == JobStatus.RUNNING.value, Job.heartbeat_at < cutoff)
            .with_for_update(skip_locked=True)
        ).all()
        now = self.clock.now()
        resumed: list[Job] = []
        failed: list[Job] = []
        for job in stale:
            job.updated_at = now
            job.worker_id = None
            if job.attempts < self.max_attempts:
                job.status = JobStatus.QUEUED.value
                resumed.append(job)
            else:
                job.status = JobStatus.FAILED.value
                job.failure_reason = WORKER_STOPPED_REASON
                job.finished_at = now
                failed.append(job)
        recovery = Recovery(
            tuple(_view(job) for job in resumed), tuple(_view(job) for job in failed)
        )
        session.commit()
        for resumed_job in recovery.resumed:
            logger.warning(
                "job resumed", extra={"event": "job.resumed", "count": resumed_job.attempts}
            )
        for _ in recovery.failed:
            logger.error("job failed after worker stop", extra={"event": "job.stale_failed"})
        return recovery
