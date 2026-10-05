"""PhotoIntake ORM model (migration 0004; DATA-005 Photo).

``photos`` holds at most one row per (user, angle): the current photo for that angle,
replaced in place on every retake, never duplicated ([IV] §2, AC5.2.4).

- ``accepted``: passed every per-photo check; ``media_file_id`` points at the stored file.
- ``rejected``: the latest upload for an angle that has no accepted photo failed a check;
  its reasons are kept so a reload shows them, the file itself is not stored.

[Decided by delivery team] No landmark signature is stored: the same-person check
recomputes signatures from the stored photos on every call ([IV] §1, §5; AC5.6.5).
The angle is free text checked against ``PHOTO_ANGLES`` by the service, so changing the
configured angles needs no migration (ASM-005). This model never leaves the module.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class PhotoStatus(StrEnum):
    """Stored status of an angle's photo (``missing`` means no row)."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CaptureMethod(StrEnum):
    """How the photo was taken ([PC] §4; informational only)."""

    UPLOAD = "upload"
    CAMERA = "camera"


_STATUSES = "', '".join(status.value for status in PhotoStatus)
_METHODS = "', '".join(method.value for method in CaptureMethod)


class Photo(Base):
    """The current photo for one of a user's angles."""

    __tablename__ = "photos"
    __table_args__ = (
        UniqueConstraint("user_id", "angle"),
        CheckConstraint(f"status IN ('{_STATUSES}')", name="status_allowed"),
        CheckConstraint(
            f"capture_method IS NULL OR capture_method IN ('{_METHODS}')",
            name="capture_method_allowed",
        ),
        CheckConstraint(
            "(status = 'accepted') = (media_file_id IS NOT NULL)", name="accepted_has_file"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    angle: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    media_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="NO ACTION"), unique=True
    )
    reasons: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    capture_method: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
