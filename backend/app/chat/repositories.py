"""Chat data access. Queries only; the service decides and commits."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.chat.models import ChatMessage, ChatUsage


def add_message(
    session: Session, *, user_id: uuid.UUID, role: str, text: str, now: datetime
) -> ChatMessage:
    """Stage a message and flush so it has its id."""
    row = ChatMessage(user_id=user_id, role=role, text=text, created_at=now)
    session.add(row)
    session.flush()
    return row


def recent_messages(session: Session, user_id: uuid.UUID, limit: int) -> list[ChatMessage]:
    """The user's latest ``limit`` messages, oldest first."""
    rows = session.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def all_messages(session: Session, user_id: uuid.UUID) -> list[ChatMessage]:
    """The user's whole conversation, oldest first."""
    return list(
        session.scalars(
            select(ChatMessage).where(ChatMessage.user_id == user_id).order_by(ChatMessage.id)
        ).all()
    )


def used_today(session: Session, user_id: uuid.UUID, day: date) -> int:
    """Replies counted (or in flight) for ``day``."""
    value = session.scalar(
        select(ChatUsage.used).where(ChatUsage.user_id == user_id, ChatUsage.day == day)
    )
    return int(value or 0)


def reserve(session: Session, user_id: uuid.UUID, day: date, limit: int) -> bool:
    """Take one of today's messages; False when ``limit`` are already taken.

    One atomic upsert: concurrent callers are serialised on the row, so exactly the free
    messages are granted (AC10.3.3). The caller commits.
    """
    upsert = (
        insert(ChatUsage)
        .values(user_id=user_id, day=day, used=1)
        .on_conflict_do_update(
            index_elements=[ChatUsage.user_id, ChatUsage.day],
            set_={"used": ChatUsage.used + 1},
            where=ChatUsage.used < limit,
        )
        .returning(ChatUsage.used)
    )
    return session.execute(upsert).first() is not None


def release(session: Session, user_id: uuid.UUID, day: date) -> None:
    """Give a reserved message back (the AI call failed, AC10.3.2). The caller commits."""
    session.execute(
        update(ChatUsage)
        .where(ChatUsage.user_id == user_id, ChatUsage.day == day, ChatUsage.used > 0)
        .values(used=ChatUsage.used - 1)
    )
