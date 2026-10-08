"""Analysis ORM models (migration 0006; DATA-009/DATA-010 groundwork).

- ``analysis_runs``: one run per payment (unique ``payment_id``: this is what makes a start
  idempotent under concurrent requests, AC7.1.3, and what limits a payment to one analysis,
  AC7.6.3). ``rerun_used`` records the one free re-run (US7.11).
- ``analysis_run_photos``: the photo files the run was started with (domain review R-02): every
  step, resume and re-run uses these ids, never the user's current photos.
- ``analysis_steps``: the four named steps and each one's saved output, so a resumed or
  re-run job skips completed steps (AC7.6.2).
- ``analysis_results``: the stored analysis result, one per run (AC7.9.3).
- ``analysis_image_slots``: the 24 image slots; U6 records them "not available yet", U7 fills
  them.

These models never leave the module.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class RunStatus(StrEnum):
    """Stored run status (contract ``AnalysisRun.status``)."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(StrEnum):
    """Stored step status; ``current`` is derived from the first step not done."""

    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"


class SlotStatus(StrEnum):
    """Stored image-slot status (U7 adds the others)."""

    NOT_AVAILABLE_YET = "not_available_yet"


_RUN_STATUSES = "', '".join(status.value for status in RunStatus)
_STEP_STATUSES = "', '".join(status.value for status in StepStatus)


class AnalysisRun(Base):
    """One paid analysis."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(f"status IN ('{_RUN_STATUSES}')", name="status_allowed"),
        CheckConstraint("failure_count >= 0", name="failure_count_not_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), unique=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16))
    rerun_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    failed_step: Mapped[str | None] = mapped_column(String(32))
    failure_reason: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisRunPhoto(Base):
    """A photo file the run was started with."""

    __tablename__ = "analysis_run_photos"
    __table_args__ = (PrimaryKeyConstraint("run_id", "angle"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    angle: Mapped[str] = mapped_column(String(32))
    media_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="NO ACTION"), index=True
    )


class AnalysisStep(Base):
    """One named step of a run and its saved output."""

    __tablename__ = "analysis_steps"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "key"),
        CheckConstraint(f"status IN ('{_STEP_STATUSES}')", name="status_allowed"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisResult(Base):
    """The stored analysis result of a completed run."""

    __tablename__ = "analysis_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnalysisImageSlot(Base):
    """One of the report's 24 AI image slots."""

    __tablename__ = "analysis_image_slots"
    __table_args__ = (PrimaryKeyConstraint("run_id", "slot_key"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    slot_key: Mapped[str] = mapped_column(String(32))
    slot_kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24))
