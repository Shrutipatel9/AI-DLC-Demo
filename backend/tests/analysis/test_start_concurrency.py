"""Two simultaneous "Start Analysis" requests make exactly one run and one job (AC7.1.3).

Real PostgreSQL with really-committing sessions: the unique ``analysis_runs.payment_id`` decides.
The payment and photo ports are small stubs (their own behaviour is covered elsewhere), so
the test needs no HTTP, photos or model. Everything created is deleted afterwards.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analysis.models import AnalysisRun
from app.analysis.services import AnalysisService
from app.jobs.models import Job
from app.jobs.public import JobQueue
from app.media.models import MediaFile
from app.payments.models import Payment
from app.payments.services import Entitlement, PaymentService
from app.photos.services import PhotoIntakeService
from app.platform.clock import SystemClock
from tests.identity.conftest import (  # noqa: F401  (two_sessions is a pytest fixture)
    TwoSessions,
    run_in_threads,
    two_sessions,
)


class StubPayments:
    def __init__(self, payment_id: uuid.UUID) -> None:
        self.payment_id = payment_id

    def require_paid(self, session: Session, user_id: uuid.UUID) -> Entitlement:
        return Entitlement(paid=True, payment_id=self.payment_id)


class StubPhotos:
    def __init__(self, files: dict[str, uuid.UUID]) -> None:
        self.files = files

    def snapshot_for_run(self, session: Session, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
        return dict(self.files)


@pytest.fixture
def race(
    committed_session_factory: Callable[[], Session],
    two_sessions: TwoSessions,  # noqa: F811
) -> Iterator[tuple[AnalysisService, uuid.UUID]]:
    user_id = two_sessions.make_user()
    payment_id = uuid.uuid4()
    files = {angle: uuid.uuid4() for angle in ("front", "left_3q", "right_3q")}
    now = datetime.now(UTC)
    with committed_session_factory() as session:
        session.add(
            Payment(
                id=payment_id,
                user_id=user_id,
                provider="fake",
                provider_session_id=None,
                amount=1999,
                currency="USD",
                status="succeeded",
                created_at=now,
                updated_at=now,
                paid_at=now,
            )
        )
        for file_id in files.values():
            session.add(
                MediaFile(
                    id=file_id,
                    owner_user_id=user_id,
                    kind="photo",
                    content_type="image/png",
                    storage_key=f"{user_id}/{file_id}.png",
                    size_bytes=1,
                    created_at=now,
                )
            )
        session.commit()
    queue = JobQueue(clock=SystemClock(), max_attempts=3, stale_after_seconds=60)
    service = AnalysisService(
        queue=queue,
        payments=cast(PaymentService, StubPayments(payment_id)),
        photos=cast(PhotoIntakeService, StubPhotos(files)),
        clock=SystemClock(),
        expected_wait_minutes=8,
    )
    try:
        yield service, user_id
    finally:
        with committed_session_factory() as session:
            job_ids = [
                job_id
                for job_id in session.scalars(
                    select(AnalysisRun.job_id).where(AnalysisRun.user_id == user_id)
                )
                if job_id is not None
            ]
            session.execute(delete(AnalysisRun).where(AnalysisRun.user_id == user_id))
            session.execute(delete(Job).where(Job.id.in_(job_ids)))
            session.commit()
        # The user (and with it the payment and files) is removed by ``two_sessions``.


def test_two_simultaneous_starts_create_exactly_one_run_and_both_return_its_id(
    race: tuple[AnalysisService, uuid.UUID],
    committed_session_factory: Callable[[], Session],
) -> None:
    service, user_id = race
    barrier = threading.Barrier(2)

    def attempt() -> Any:
        with committed_session_factory() as session:
            barrier.wait(timeout=5)
            return service.start(session, user_id)

    first, second = run_in_threads(attempt, attempt)

    assert not isinstance(first, Exception), first
    assert not isinstance(second, Exception), second
    assert first.run_id == second.run_id
    with committed_session_factory() as session:
        runs = session.scalar(
            select(func.count()).select_from(AnalysisRun).where(AnalysisRun.user_id == user_id)
        )
        jobs = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.kind == "analysis.run", Job.status == "queued")
        )
        assert runs == 1
        run_job_id = session.scalars(
            select(AnalysisRun.job_id).where(AnalysisRun.user_id == user_id)
        ).one()
        assert run_job_id is not None
        assert jobs is not None
        assert jobs >= 1
        owned = session.scalar(select(func.count()).select_from(Job).where(Job.id == run_job_id))
        assert owned == 1  # the loser's job was rolled back with its savepoint
