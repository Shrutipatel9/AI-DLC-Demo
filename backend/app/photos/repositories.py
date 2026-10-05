"""PhotoIntake data access. Repositories never commit; the calling service owns the transaction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.photos.models import Photo, PhotoStatus


def find_all(session: Session, user_id: uuid.UUID) -> list[Photo]:
    """Every stored photo row of the user (one per angle at most)."""
    return list(session.scalars(select(Photo).where(Photo.user_id == user_id)))


def lock_photo(session: Session, user_id: uuid.UUID, angle: str, now: datetime) -> Photo:
    """The user's row for ``angle``, created if missing and locked ``FOR UPDATE``.

    ``INSERT ... ON CONFLICT DO NOTHING`` first, so two concurrent first uploads for one angle
    cannot collide on the unique ``(user_id, angle)``; the lock serialises them. A row created
    here starts as ``rejected`` with no reasons and is completed by the caller in the same
    transaction (it never commits in that state).
    """
    session.execute(
        pg_insert(Photo)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            angle=angle,
            status=PhotoStatus.REJECTED.value,
            media_file_id=None,
            reasons=[],
            capture_method=None,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "angle"])
    )
    return session.scalars(
        select(Photo)
        .where(Photo.user_id == user_id, Photo.angle == angle)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
