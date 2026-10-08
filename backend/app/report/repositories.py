"""Report data access. Queries only; the service decides and commits."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.report.models import ReportPdf


def find_pdf(session: Session, run_id: uuid.UUID, *, lock: bool = False) -> ReportPdf | None:
    """The cached PDF row of a run (``FOR UPDATE`` when ``lock``)."""
    statement = select(ReportPdf).where(ReportPdf.run_id == run_id)
    if lock:
        statement = statement.with_for_update()
    return session.scalars(statement).one_or_none()


def add_pdf(
    session: Session,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    media_file_id: uuid.UUID,
    fingerprint: str,
    now: datetime,
) -> None:
    """Stage a new cache row and flush, so a concurrent first download fails here."""
    session.add(
        ReportPdf(
            run_id=run_id,
            user_id=user_id,
            media_file_id=media_file_id,
            fingerprint=fingerprint,
            created_at=now,
        )
    )
    session.flush()
