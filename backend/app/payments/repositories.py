"""Payments data access. Repositories never commit; the calling service owns the transaction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.payments.models import Payment, PaymentEvent, PaymentStatus


def add_payment(session: Session, payment: Payment) -> Payment:
    """Stage a new payment row."""
    session.add(payment)
    session.flush()
    return payment


def find_succeeded(session: Session, user_id: uuid.UUID) -> Payment | None:
    """The user's earliest successful payment, if any."""
    return session.scalars(
        select(Payment)
        .where(Payment.user_id == user_id, Payment.status == PaymentStatus.SUCCEEDED.value)
        .order_by(Payment.paid_at, Payment.created_at)
        .limit(1)
    ).first()


def find_latest(session: Session, user_id: uuid.UUID) -> Payment | None:
    """The user's most recent payment attempt, if any."""
    return session.scalars(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
        .limit(1)
    ).first()


def list_for_user(session: Session, user_id: uuid.UUID) -> list[Payment]:
    """All the user's payment attempts, newest first."""
    return list(
        session.scalars(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
        )
    )


def lock_by_session_id(session: Session, provider_session_id: str) -> Payment | None:
    """The payment for a provider Checkout session, locked ``FOR UPDATE``."""
    return session.scalars(
        select(Payment)
        .where(Payment.provider_session_id == provider_session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def lock_by_id(session: Session, payment_id: uuid.UUID) -> Payment | None:
    """The payment by id, locked ``FOR UPDATE``."""
    return session.scalars(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def record_event(
    session: Session, provider_event_id: str, event_type: str, now: datetime
) -> uuid.UUID | None:
    """Insert the processed-event row; ``None`` when this event id was already recorded.

    ``INSERT ... ON CONFLICT DO NOTHING`` on the unique event id: a concurrent duplicate
    waits for the first transaction and then inserts nothing, so each event is handled once
    (AC6.3.2).
    """
    return session.execute(
        pg_insert(PaymentEvent)
        .values(
            id=uuid.uuid4(),
            provider_event_id=provider_event_id,
            event_type=event_type,
            payment_id=None,
            received_at=now,
        )
        .on_conflict_do_nothing(index_elements=["provider_event_id"])
        .returning(PaymentEvent.id)
    ).scalar_one_or_none()


def link_event(session: Session, event_row_id: uuid.UUID, payment_id: uuid.UUID) -> None:
    """Point a processed-event row at the payment it concerned."""
    event = session.get(PaymentEvent, event_row_id)
    if event is not None:
        event.payment_id = payment_id
        session.flush()
