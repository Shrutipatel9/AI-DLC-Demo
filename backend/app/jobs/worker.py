"""The worker: claims jobs, runs their handlers and records the outcome (US1.7).

One worker process runs one job at a time. While a handler runs, a small thread refreshes the
job's heartbeat, so a long vendor call is not mistaken for a dead worker. When the process
dies, the next ``run_once`` (in this or another worker) finds the stale job and resumes or
fails it (AC1.7.2).

A handler raises :class:`JobFailure` with a plain-language reason for an expected failure;
any other exception ends the job as failed with a generic reason. Only the event name and the
exception class are logged: never photo data, answer text or a message that might carry them
(AC1.7.3).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.jobs.service import ClaimedJob, JobQueue, JobView
from app.platform.db import SessionFactory

logger = logging.getLogger("jobs")

GENERIC_FAILURE = "The job stopped unexpectedly."


class JobFailure(Exception):  # noqa: N818  (reads better at the raise site)
    """An expected failure. ``reason`` is plain language and safe to store and show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class JobContext:
    """What a handler receives."""

    job_id: uuid.UUID
    payload: dict[str, Any]
    attempt: int
    set_step: Callable[[str], None]


JobHandler = Callable[[JobContext], dict[str, Any] | None]
FailureHook = Callable[[JobView], None]


class Worker:
    """Runs jobs from a :class:`JobQueue`.

    Args:
        queue: The job queue.
        session_factory: Creates the worker's database sessions.
        handlers: ``kind -> handler``.
        worker_id: A label for the job row (no personal data).
        failure_hooks: ``kind -> hook`` called when a job of that kind ends failed without its
            handler finishing (for example after a dead worker's last attempt), so the owner
            of the work can record the failure too.
        heartbeat_seconds: Heartbeat period; ``None`` disables the thread (tests).
        poll_interval_seconds: Sleep between polls when idle.
        sleep: Sleep function (tests inject one).
    """

    def __init__(
        self,
        *,
        queue: JobQueue,
        session_factory: SessionFactory,
        handlers: Mapping[str, JobHandler],
        worker_id: str | None = None,
        failure_hooks: Mapping[str, FailureHook] | None = None,
        heartbeat_seconds: float | None = None,
        poll_interval_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.queue = queue
        self.session_factory = session_factory
        self.handlers = dict(handlers)
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.failure_hooks = dict(failure_hooks or {})
        self.heartbeat_seconds = heartbeat_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._sleep = sleep

    def run_once(self) -> bool:
        """Recover stale jobs, then run at most one job. True when a job was run."""
        with self.session_factory() as session:
            recovery = self.queue.recover_stale(session)
        for failed in recovery.failed:
            self._notify_failed(failed)
        with self.session_factory() as session:
            claimed = self.queue.claim_next(session, self.worker_id, frozenset(self.handlers))
        if claimed is None:
            return False
        self._run(claimed)
        return True

    def run_forever(self, stop: threading.Event) -> None:
        """Poll until ``stop`` is set."""
        logger.info("worker started", extra={"event": "worker.started"})
        while not stop.is_set():
            try:
                busy = self.run_once()
            except Exception as exc:
                # The database or the queue itself failed: keep the process alive and retry.
                logger.error(
                    "worker loop error",
                    extra={"event": "worker.loop_error", "errorClass": type(exc).__name__},
                )
                busy = False
            if not busy:
                stop.wait(self.poll_interval_seconds)
        logger.info("worker stopped", extra={"event": "worker.stopped"})

    # ----------------------------------------------------------------------------------------
    def _run(self, claimed: ClaimedJob) -> None:
        handler = self.handlers[claimed.kind]
        stop_beat = threading.Event()
        beat = self._start_heartbeat(claimed.id, stop_beat)

        def set_step(step: str) -> None:
            with self.session_factory() as session:
                self.queue.heartbeat(session, claimed.id, step)

        context = JobContext(claimed.id, claimed.payload, claimed.attempts, set_step)
        try:
            result = handler(context)
        except JobFailure as failure:
            self._finish_failed(claimed, failure.reason)
        except Exception as exc:
            logger.error(
                "job handler error",
                extra={"event": "job.handler_error", "errorClass": type(exc).__name__},
            )
            self._finish_failed(claimed, GENERIC_FAILURE)
        else:
            with self.session_factory() as session:
                self.queue.complete(session, claimed.id, result)
            logger.info("job completed", extra={"event": "job.completed"})
        finally:
            stop_beat.set()
            if beat is not None:
                beat.join(timeout=5)

    def _finish_failed(self, claimed: ClaimedJob, reason: str) -> None:
        with self.session_factory() as session:
            self.queue.fail(session, claimed.id, reason)
            view = self.queue.get(session, claimed.id)
        logger.error("job failed", extra={"event": "job.failed"})
        if view is not None:
            self._notify_failed(view)

    def _notify_failed(self, job: JobView) -> None:
        hook = self.failure_hooks.get(job.kind)
        if hook is None:
            return
        try:
            hook(job)
        except Exception as exc:
            logger.error(
                "job failure hook error",
                extra={"event": "job.hook_error", "errorClass": type(exc).__name__},
            )

    def _start_heartbeat(self, job_id: uuid.UUID, stop: threading.Event) -> threading.Thread | None:
        period = self.heartbeat_seconds
        if period is None:
            return None

        def beat() -> None:
            while not stop.wait(period):
                try:
                    with self.session_factory() as session:
                        self.queue.heartbeat(session, job_id)
                except Exception as exc:
                    logger.error(
                        "heartbeat failed",
                        extra={"event": "job.heartbeat_error", "errorClass": type(exc).__name__},
                    )

        thread = threading.Thread(target=beat, name="job-heartbeat", daemon=True)
        thread.start()
        return thread
