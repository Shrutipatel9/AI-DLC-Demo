"""The Jobs module's public interface (US1.7). Other modules import only this.

- ``build_job_queue``: the queue from settings (used by the API and the worker).
- ``Worker`` / ``JobFailure`` / ``JobContext``: the worker loop and what a handler sees.
- ``JobQueue.enqueue`` stages a job in the caller's transaction; ``get`` reads its status and
  current step by id.
"""

from __future__ import annotations

from app.jobs.models import JobStatus
from app.jobs.service import ClaimedJob, JobQueue, JobView, Recovery
from app.jobs.worker import FailureHook, JobContext, JobFailure, JobHandler, Worker
from app.platform.clock import Clock
from app.platform.settings import Settings

__all__ = [
    "ClaimedJob",
    "FailureHook",
    "JobContext",
    "JobFailure",
    "JobHandler",
    "JobQueue",
    "JobStatus",
    "JobView",
    "Recovery",
    "Worker",
    "build_job_queue",
]


def build_job_queue(settings: Settings, *, clock: Clock) -> JobQueue:
    """Create the queue from settings."""
    return JobQueue(
        clock=clock,
        max_attempts=settings.job_max_attempts,
        stale_after_seconds=settings.worker_stale_after_seconds,
    )
