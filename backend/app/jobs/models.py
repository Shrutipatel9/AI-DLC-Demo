"""Background job ORM model (migration 0006; US1.7).

``jobs`` is the queue: one row per unit of background work. A worker claims a ``queued`` row
with ``FOR UPDATE SKIP LOCKED``, marks it ``running`` and refreshes ``heartbeat_at`` while it
works. The row keeps the current step, a small result and a failure reason, so a web request
can read a job's progress by id (AC1.7.1).

The payload holds ids only. Photo data, answers and tokens never enter this table (AC1.7.3).
This model never leaves the jobs module.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class JobStatus(StrEnum):
    """Stored job status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


_STATUSES = "', '".join(status.value for status in JobStatus)


class Job(Base):
    """One unit of background work."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(f"status IN ('{_STATUSES}')", name="status_allowed"),
        CheckConstraint("attempts >= 0", name="attempts_not_negative"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(16))
    current_step: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failure_reason: Mapped[str | None] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    worker_id: Mapped[str | None] = mapped_column(String(64))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
