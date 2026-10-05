"""Payments ORM models (migration 0005; DATA-008 Payment).

- ``payments``: one row per checkout attempt. It is created ``pending`` before the provider is
  called, gets the provider's session id once the hosted Checkout exists, and changes status
  only through a verified webhook (FR7.4): ``succeeded``, or ``failed`` when the session
  expired or an asynchronous payment failed (contract C2). The amount and currency are the
  configured price at checkout time (FR-016).
- ``payment_events``: every processed webhook event, keyed by the provider's event id. The
  unique constraint makes the webhook idempotent even under concurrent delivery: a repeated
  event id never changes anything twice (AC6.3.2, FR7.5).

These models never leave the module.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class PaymentStatus(StrEnum):
    """Stored payment status (contract C1 ``PaymentRecord.status``)."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_STATUSES = "', '".join(status.value for status in PaymentStatus)


class Payment(Base):
    """One checkout attempt and its outcome."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(f"status IN ('{_STATUSES}')", name="status_allowed"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("char_length(currency) = 3", name="currency_code"),
        CheckConstraint("(status = 'succeeded') = (paid_at IS NOT NULL)", name="paid_at_set"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(16))
    provider_session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEvent(Base):
    """A processed provider webhook event (idempotency record)."""

    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_event_id: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    #: The payment the event changed or referred to; NULL for events about unknown sessions.
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), index=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
