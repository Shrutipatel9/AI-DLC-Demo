"""Chat ORM models (migration 0009): the conversation and the per-day usage counter."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class ChatMessage(Base):
    """One message of a user's conversation (``role`` is ``user`` or ``assistant``)."""

    __tablename__ = "chat_messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="role_allowed"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChatUsage(Base):
    """Replies counted (or in flight) for a user on a UTC day.

    ``used`` includes a reservation taken before the AI call and given back if it fails, so
    the database alone decides who gets the last message (AC10.3.3).
    """

    __tablename__ = "chat_usage"
    __table_args__ = (CheckConstraint("used >= 0", name="used_not_negative"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    used: Mapped[int] = mapped_column(BigInteger)
