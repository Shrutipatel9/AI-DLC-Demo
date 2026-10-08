"""Analysis data access. Queries only; the services decide and commit."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.analysis.models import (
    AnalysisImageSlot,
    AnalysisResult,
    AnalysisRun,
    AnalysisRunPhoto,
    AnalysisStep,
    StepStatus,
)


def find_run(session: Session, run_id: uuid.UUID, *, lock: bool = False) -> AnalysisRun | None:
    """The run by id (``FOR UPDATE`` when ``lock``)."""
    statement = select(AnalysisRun).where(AnalysisRun.id == run_id)
    if lock:
        statement = statement.with_for_update()
    return session.scalars(statement).one_or_none()


def find_run_for_payment(session: Session, payment_id: uuid.UUID) -> AnalysisRun | None:
    """The one run of a payment, if any."""
    return session.scalars(
        select(AnalysisRun).where(AnalysisRun.payment_id == payment_id)
    ).one_or_none()


def find_latest_run(session: Session, user_id: uuid.UUID) -> AnalysisRun | None:
    """The user's newest run."""
    return session.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.user_id == user_id)
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    ).one_or_none()


def find_run_for_job(session: Session, job_id: uuid.UUID) -> AnalysisRun | None:
    """The run a job belongs to."""
    return session.scalars(select(AnalysisRun).where(AnalysisRun.job_id == job_id)).one_or_none()


def add_run(session: Session, run: AnalysisRun) -> None:
    """Stage a run and flush, so a duplicate payment fails here."""
    session.add(run)
    session.flush()


def add_photos(session: Session, run_id: uuid.UUID, snapshot: Mapping[str, uuid.UUID]) -> None:
    """Record the photo files the run starts with."""
    session.add_all(
        AnalysisRunPhoto(run_id=run_id, angle=angle, media_file_id=file_id)
        for angle, file_id in snapshot.items()
    )


def list_photos(session: Session, run_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """``angle -> file id`` recorded for the run."""
    rows = session.scalars(select(AnalysisRunPhoto).where(AnalysisRunPhoto.run_id == run_id)).all()
    return {row.angle: row.media_file_id for row in rows}


def add_steps(session: Session, run_id: uuid.UUID, keys: Iterable[str]) -> None:
    """Create the steps, all waiting."""
    session.add_all(
        AnalysisStep(run_id=run_id, key=key, status=StepStatus.WAITING.value) for key in keys
    )


def list_steps(session: Session, run_id: uuid.UUID) -> dict[str, AnalysisStep]:
    """The run's steps by key."""
    rows = session.scalars(select(AnalysisStep).where(AnalysisStep.run_id == run_id)).all()
    return {row.key: row for row in rows}


def mark_step_done(
    session: Session, run_id: uuid.UUID, key: str, output: dict[str, Any], now: datetime
) -> None:
    """Save a step's output and mark it done."""
    step = session.get(AnalysisStep, (run_id, key))
    assert step is not None  # noqa: S101  (steps are created with the run)
    step.status = StepStatus.DONE.value
    step.output = output
    step.completed_at = now


def mark_step_failed(session: Session, run_id: uuid.UUID, key: str) -> None:
    """Mark a step failed (its output stays empty)."""
    step = session.get(AnalysisStep, (run_id, key))
    assert step is not None  # noqa: S101
    step.status = StepStatus.FAILED.value


def reset_failed_steps(session: Session, run_id: uuid.UUID) -> None:
    """Make failed steps waiting again for the free re-run; done steps stay done."""
    for step in list_steps(session, run_id).values():
        if step.status == StepStatus.FAILED.value:
            step.status = StepStatus.WAITING.value


def find_result(session: Session, run_id: uuid.UUID) -> AnalysisResult | None:
    """The stored result of a run."""
    return session.get(AnalysisResult, run_id)


def add_result(
    session: Session, run_id: uuid.UUID, user_id: uuid.UUID, result: dict[str, Any], now: datetime
) -> None:
    """Store the analysis result."""
    session.add(AnalysisResult(run_id=run_id, user_id=user_id, result=result, created_at=now))


def list_slots(session: Session, run_id: uuid.UUID) -> list[AnalysisImageSlot]:
    """The run's image slots."""
    return list(
        session.scalars(select(AnalysisImageSlot).where(AnalysisImageSlot.run_id == run_id)).all()
    )


def add_slots(session: Session, slots: Iterable[AnalysisImageSlot]) -> None:
    """Stage image slots."""
    session.add_all(slots)


def find_slot(
    session: Session, run_id: uuid.UUID, slot_key: str, *, lock: bool = False
) -> AnalysisImageSlot | None:
    """One image slot (``FOR UPDATE`` when ``lock``)."""
    statement = select(AnalysisImageSlot).where(
        AnalysisImageSlot.run_id == run_id, AnalysisImageSlot.slot_key == slot_key
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalars(statement).one_or_none()


def media_in_use(session: Session, file_id: uuid.UUID) -> bool:
    """Whether any run was started with this file, or shows it as a generated image."""
    return bool(
        session.scalar(select(exists().where(AnalysisRunPhoto.media_file_id == file_id)))
        or session.scalar(select(exists().where(AnalysisImageSlot.media_file_id == file_id)))
    )
