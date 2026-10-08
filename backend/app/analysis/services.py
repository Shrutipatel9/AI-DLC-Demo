"""Starting, reading and re-running an analysis (US7.1, US7.2, US7.11).

Rules:
- A start needs a successful payment (402 first) and a complete, consistent photo set (409), in
  the order of contract C11 (AC6.4.2); both come from ``payments.paid_photo_snapshot``. It is
  only ever called from the user's explicit "Start Analysis" request, never from the Stripe
  webhook (FR-015, BR-001).
- One run per payment: the unique ``payment_id`` makes a start idempotent under concurrent
  requests (AC7.1.3). A second start returns the same run while it is not complete, and fails
  with 409 ``ANALYSIS_ALREADY_COMPLETE`` after it is (AC7.1.4), without any vendor call.
- The photo files are recorded at start; the worker only ever uses those (R-02).
- A failed run can be re-run once for free (US7.11): completed steps are kept and not repeated.
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analysis import repositories
from app.analysis.domain import (
    FAILURE_MESSAGE,
    FAILURE_MESSAGE_FINAL,
    JOB_KIND,
    STEP_KEYS,
    RunView,
    StepState,
)
from app.analysis.models import AnalysisRun, RunStatus, StepStatus
from app.jobs.public import JobQueue
from app.payments.public import Entitlement, PaymentService, paid_photo_snapshot, require_paid
from app.photos.public import PhotoIntakeService
from app.platform.clock import Clock
from app.platform.errors import AnalysisAlreadyComplete, NotFound, RerunNotAvailable

logger = logging.getLogger("analysis")


class AnalysisService:
    """Analysis use cases for the API process. Public methods commit their own work.

    Args:
        queue: The job queue (the run's job is created in the same transaction).
        payments: The payments service (C5).
        photos: The photo-intake service (C4).
        clock: Time source.
        expected_wait_minutes: Shown on the progress screen (AC7.2.2).
    """

    def __init__(
        self,
        *,
        queue: JobQueue,
        payments: PaymentService,
        photos: PhotoIntakeService,
        clock: Clock,
        expected_wait_minutes: int,
    ) -> None:
        self.queue = queue
        self.payments = payments
        self.photos = photos
        self.clock = clock
        self.expected_wait_minutes = expected_wait_minutes

    # --- Start --------------------------------------------------------------------------------

    def start(self, session: Session, user_id: uuid.UUID) -> RunView:
        """Start the analysis, or return the run that is already going (AC7.1.1-AC7.1.4).

        Raises:
            PaymentRequired: 402 when no payment has succeeded.
            PhotoSetIncomplete: 409 when an angle has no accepted photo.
            PhotoIdentityMismatch: 409 when the same-person check fails now (AC7.1.2).
            AnalysisAlreadyComplete: 409 when the paid analysis already finished.
        """
        entitlement = require_paid(self.payments, session, user_id)
        payment_id = _payment_id(entitlement)
        existing = repositories.find_run_for_payment(session, payment_id)
        if existing is not None:
            return self._existing(session, existing)

        snapshot = paid_photo_snapshot(self.payments, self.photos, session, user_id)
        try:
            with session.begin_nested():
                run = self._create_run(session, user_id, payment_id, snapshot)
        except IntegrityError:
            # A concurrent start won the unique payment id: return its run (AC7.1.3).
            session.rollback()
            winner = repositories.find_run_for_payment(session, payment_id)
            if winner is None:
                raise
            return self._existing(session, winner)
        session.commit()
        logger.info("analysis started", extra={"event": "analysis.started", "userId": str(user_id)})
        return self.view(session, run)

    def _existing(self, session: Session, run: AnalysisRun) -> RunView:
        if run.status == RunStatus.COMPLETED.value:
            raise AnalysisAlreadyComplete()
        return self.view(session, run)

    def _create_run(
        self,
        session: Session,
        user_id: uuid.UUID,
        payment_id: uuid.UUID,
        snapshot: dict[str, uuid.UUID],
    ) -> AnalysisRun:
        now = self.clock.now()
        run = AnalysisRun(
            id=uuid.uuid4(),
            user_id=user_id,
            payment_id=payment_id,
            status=RunStatus.RUNNING.value,
            rerun_used=False,
            failure_count=0,
            started_at=now,
            updated_at=now,
        )
        repositories.add_run(session, run)
        repositories.add_photos(session, run.id, snapshot)
        repositories.add_steps(session, run.id, STEP_KEYS)
        run.job_id = self.queue.enqueue(session, JOB_KIND, {"runId": str(run.id)})
        session.flush()
        return run

    # --- Read ---------------------------------------------------------------------------------

    def current(self, session: Session, user_id: uuid.UUID) -> RunView:
        """The user's current run (steps, wait, failure, re-run availability).

        Raises:
            NotFound: 404 when the user has no run.
        """
        run = repositories.find_latest_run(session, user_id)
        if run is None:
            raise NotFound("You haven't started an analysis yet.")
        return self.view(session, run)

    def view(self, session: Session, run: AnalysisRun) -> RunView:
        """Build the progress view of ``run``."""
        statuses = {
            key: step.status for key, step in repositories.list_steps(session, run.id).items()
        }
        steps: list[tuple[str, StepState]] = []
        current_assigned = False
        for key in STEP_KEYS:
            status = statuses.get(key, StepStatus.WAITING.value)
            state: StepState
            if run.status == RunStatus.COMPLETED.value or status == StepStatus.DONE.value:
                state = "done"
            elif status == StepStatus.FAILED.value or (
                run.status == RunStatus.FAILED.value and key == run.failed_step
            ):
                state = "failed"
            elif run.status == RunStatus.RUNNING.value and not current_assigned:
                state, current_assigned = "current", True
            else:
                state = "waiting"
            steps.append((key, state))
        failed = run.status == RunStatus.FAILED.value
        contact_support = failed and run.rerun_used
        return RunView(
            run_id=run.id,
            status=cast(Literal["running", "completed", "failed"], run.status),
            steps=tuple(steps),
            rerun_available=failed and not run.rerun_used,
            failure_message=(FAILURE_MESSAGE_FINAL if contact_support else FAILURE_MESSAGE)
            if failed
            else None,
            contact_support=contact_support,
            expected_wait_minutes=self.expected_wait_minutes,
        )

    # --- Re-run -------------------------------------------------------------------------------

    def rerun(self, session: Session, user_id: uuid.UUID) -> RunView:
        """The one free re-run of a failed run; completed steps are kept (US7.11).

        Raises:
            NotFound: 404 when the user has no run.
            RerunNotAvailable: 409 when the run has not failed or the re-run was used.
        """
        latest = repositories.find_latest_run(session, user_id)
        if latest is None:
            raise NotFound("You haven't started an analysis yet.")
        run = repositories.find_run(session, latest.id, lock=True)
        assert run is not None  # noqa: S101  (it was just read)
        if run.status != RunStatus.FAILED.value or run.rerun_used:
            raise RerunNotAvailable()
        repositories.reset_failed_steps(session, run.id)
        run.status = RunStatus.RUNNING.value
        run.rerun_used = True
        run.updated_at = self.clock.now()
        run.job_id = self.queue.enqueue(session, JOB_KIND, {"runId": str(run.id)})
        session.commit()
        logger.info("analysis re-run", extra={"event": "analysis.rerun", "userId": str(user_id)})
        return self.view(session, run)


def _payment_id(entitlement: Entitlement) -> uuid.UUID:
    assert entitlement.payment_id is not None  # noqa: S101  (a paid entitlement has a payment)
    return entitlement.payment_id
