"""MediaStore ORM model (migration 0004).

``media_files`` holds one row per stored file: its owner, kind, content type and the key
under which the FileStorage adapter keeps the bytes. The bytes themselves are never in the
database. This model never leaves the media module.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class MediaKind(StrEnum):
    """What a stored file is."""

    PHOTO = "photo"
    AI_IMAGE = "ai_image"
    REPORT_PDF = "report_pdf"


_KINDS = "', '".join(kind.value for kind in MediaKind)


class MediaFile(Base):
    """One privately stored file."""

    __tablename__ = "media_files"
    __table_args__ = (
        CheckConstraint(f"kind IN ('{_KINDS}')", name="kind_allowed"),
        CheckConstraint("size_bytes >= 0", name="size_not_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    content_type: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
