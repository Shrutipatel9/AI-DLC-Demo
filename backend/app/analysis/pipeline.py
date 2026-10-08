"""The analysis pipeline (contract C7 step hook; US7.6): runs a run's steps in order.

Steps register with ``register_step(name, order, handler)`` (providers: FaceMeasurement and
ReportWriting here, ImageGeneration in U7, Report in U8). A handler gets a :class:`RunContext`
and returns a :class:`StepResult`; it must be idempotent. The pipeline saves each step's output
before moving on, so a restart or the free re-run skips completed steps and makes no second paid
call for them (AC7.6.2). The run's photo files come from its start-time snapshot, never from
the user's current photos (R-02).

Failures: a step that returns ``failed`` (or raises) marks that step and the run failed, then
fails the job; the progress screen shows plain language, never the reason (US7.11).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.analysis import repositories
from app.analysis.domain import STEP_KEYS
from app.analysis.models import RunStatus, StepStatus
from app.jobs.public import JobContext, JobFailure, JobView
from app.platform.clock import Clock
from app.platform.db import SessionFactory

logger = logging.getLogger("analysis")

GENERIC_STEP_FAILURE = "A step of the analysis failed."


@dataclass(frozen=True)
class StepResult:
    """What a step handler returns."""

    status: Literal["done", "failed"]
    reason: str | None = None
    output: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunContext:
    """What a step handler gets (contract C7 ``RunContext``).

    Attributes:
        run_id: The run.
        user_id: The verified owner, from the run record.
        photo_snapshot: ``angle -> media file id`` recorded when the run started.
        outputs: Saved outputs of the steps already done, by step key.
        session_factory: For short database sessions (never held across a vendor call).
    """

    run_id: uuid.UUID
    user_id: uuid.UUID
    photo_snapshot: dict[str, uuid.UUID]
    outputs: dict[str, dict[str, Any]]
    session_factory: SessionFactory


class StepHandler(Protocol):
    """A pipeline step."""

    def __call__(self, ctx: RunContext) -> StepResult:
        """Run the step; idempotent."""
        ...


class AnalysisPipeline:
    """Runs analysis jobs.

    Args:
        session_factory: Database sessions for the worker.
        clock: Time source.
    """

    def __init__(self, *, session_factory: SessionFactory, clock: Clock) -> None:
        self.session_factory = session_factory
        self.clock = clock
        self._steps: dict[str, tuple[int, StepHandler]] = {}

    def register_step(self, name: str, order: int, handler: StepHandler) -> None:
        """Register (or replace) a step (contract C7 ``register_step``).

        Raises:
            ValueError: For a name that is not one of the named steps.
        """
        if name not in STEP_KEYS:
            raise ValueError(f"unknown analysis step {name!r}")
        self._steps[name] = (order, handler)

    def registered_steps(self) -> list[str]:
        """Step names in execution order."""
        return [name for name, _ in sorted(self._steps.items(), key=lambda item: item[1][0])]

    # --- Job handler --------------------------------------------------------------------------

    def handle(self, job: JobContext) -> dict[str, Any] | None:
        """The ``analysis.run`` job handler.

        Raises:
            JobFailure: When a step failed (the run is already marked failed).
        """
        run_id = uuid.UUID(str(job.payload["runId"]))
        with self.session_factory() as session:
            run = repositories.find_run(session, run_id)
            if run is None or run.status == RunStatus.FAILED.value:
                raise JobFailure("The analysis run is not available.")
            if run.status == RunStatus.COMPLETED.value:
                return {"runId": str(run_id)}
            user_id = run.user_id
            snapshot = repositories.list_photos(session, run_id)
            statuses = {
                key: (step.status, step.output)
                for key, step in repositories.list_steps(session, run_id).items()
            }
        outputs = {
            key: output or {} for key, (status, output) in statuses.items() if status == "done"
        }
        ctx = RunContext(run_id, user_id, snapshot, outputs, self.session_factory)
        for name in self.registered_steps():
            if statuses.get(name, ("waiting", None))[0] == StepStatus.DONE.value:
                continue  # completed before a restart or the re-run: never repeated (AC7.6.2)
            job.set_step(name)
            self._run_step(name, ctx)
        self._complete(run_id)
        return {"runId": str(run_id)}

    def _run_step(self, name: str, ctx: RunContext) -> None:
        handler = self._steps[name][1]
        try:
            result = handler(ctx)
        except Exception as exc:
            logger.error(
                "analysis step error",
                extra={
                    "event": "analysis.step_error",
                    "reason": name,
                    "errorClass": type(exc).__name__,
                },
            )
            self._fail(ctx.run_id, name, GENERIC_STEP_FAILURE)
            raise JobFailure(GENERIC_STEP_FAILURE) from None
        if result.status == "failed":
            reason = result.reason or GENERIC_STEP_FAILURE
            logger.error(
                "analysis step failed", extra={"event": "analysis.step_failed", "reason": name}
            )
            self._fail(ctx.run_id, name, reason)
            raise JobFailure(reason)
        with self.session_factory() as session:
            repositories.mark_step_done(session, ctx.run_id, name, result.output, self.clock.now())
            session.commit()
        ctx.outputs[name] = result.output

    def _complete(self, run_id: uuid.UUID) -> None:
        with self.session_factory() as session:
            run = repositories.find_run(session, run_id, lock=True)
            if run is not None and run.status == RunStatus.RUNNING.value:
                now = self.clock.now()
                run.status = RunStatus.COMPLETED.value
                run.completed_at = now
                run.updated_at = now
                run.failed_step = None
                run.failure_reason = None
            session.commit()
        logger.info("analysis completed", extra={"event": "analysis.completed"})

    def _fail(self, run_id: uuid.UUID, step: str, reason: str) -> None:
        with self.session_factory() as session:
            run = repositories.find_run(session, run_id, lock=True)
            if run is not None and run.status == RunStatus.RUNNING.value:
                repositories.mark_step_failed(session, run_id, step)
                run.status = RunStatus.FAILED.value
                run.failure_count += 1
                run.failed_step = step
                run.failure_reason = reason[:500]
                run.updated_at = self.clock.now()
            session.commit()

    def on_job_failed(self, job: JobView) -> None:
        """Mark the run failed when its job ended failed without its handler finishing it.

        This is the dead worker's last attempt (AC1.7.2).
        """
        with self.session_factory() as session:
            run = repositories.find_run_for_job(session, job.id)
            if run is None or run.status != RunStatus.RUNNING.value:
                return
            step = job.current_step if job.current_step in STEP_KEYS else STEP_KEYS[0]
            run.status = RunStatus.FAILED.value
            run.failure_count += 1
            run.failed_step = step
            run.failure_reason = (job.failure_reason or GENERIC_STEP_FAILURE)[:500]
            run.updated_at = self.clock.now()
            repositories.mark_step_failed(session, run.id, step)
            session.commit()
