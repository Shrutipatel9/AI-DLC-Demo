"""MediaStore data access. Repositories never commit; the calling service owns the transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.media.models import MediaFile


def add(session: Session, record: MediaFile) -> MediaFile:
    """Stage a new file record."""
    session.add(record)
    session.flush()
    return record


def find(session: Session, file_id: uuid.UUID) -> MediaFile | None:
    """The file record, whoever owns it (callers check ownership)."""
    return session.get(MediaFile, file_id)


def find_owned(session: Session, file_id: uuid.UUID, owner_user_id: uuid.UUID) -> MediaFile | None:
    """The file record only when ``owner_user_id`` owns it."""
    return session.scalars(
        select(MediaFile).where(MediaFile.id == file_id, MediaFile.owner_user_id == owner_user_id)
    ).one_or_none()


def remove(session: Session, file_id: uuid.UUID) -> None:
    """Delete the file record."""
    session.execute(delete(MediaFile).where(MediaFile.id == file_id))
