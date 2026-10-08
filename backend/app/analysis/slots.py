"""The report's 24 image slots as other modules see them (contract C7; U7 ImageGeneration).

The ImageGeneration module fills and reads the slots through these functions; the rows and the
models stay inside the analysis module. Each function runs in the caller's session and does not
commit, except where noted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.analysis import repositories
from app.analysis.models import AnalysisImageSlot, SlotStatus


@dataclass(frozen=True)
class SlotView:
    """One image slot."""

    run_id: uuid.UUID
    slot_key: str
    slot_kind: str
    status: str
    media_file_id: uuid.UUID | None
    auto_attempts: int
    manual_retries: int


@dataclass(frozen=True)
class RunRef:
    """What ImageGeneration needs to know about a run."""

    run_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    photo_snapshot: dict[str, uuid.UUID]


def _view(slot: AnalysisImageSlot) -> SlotView:
    return SlotView(
        run_id=slot.run_id,
        slot_key=slot.slot_key,
        slot_kind=slot.slot_kind,
        status=slot.status,
        media_file_id=slot.media_file_id,
        auto_attempts=slot.auto_attempts,
        manual_retries=slot.manual_retries,
    )


def latest_run_ref(session: Session, user_id: uuid.UUID) -> RunRef | None:
    """The user's newest run (its owner is the verified ``user_id``)."""
    run = repositories.find_latest_run(session, user_id)
    if run is None:
        return None
    return RunRef(run.id, run.user_id, run.status, repositories.list_photos(session, run.id))


def list_slot_views(session: Session, run_id: uuid.UUID) -> list[SlotView]:
    """The run's slots."""
    return [_view(slot) for slot in repositories.list_slots(session, run_id)]


def find_slot_view(session: Session, run_id: uuid.UUID, slot_key: str) -> SlotView | None:
    """One slot of the run."""
    slot = repositories.find_slot(session, run_id, slot_key)
    return None if slot is None else _view(slot)


def ensure_slots(session: Session, run_id: uuid.UUID, slots: dict[str, str]) -> None:
    """Create the missing slots (``slot_key -> kind``) as ``pending``; existing ones stay."""
    existing = {slot.slot_key for slot in repositories.list_slots(session, run_id)}
    repositories.add_slots(
        session,
        (
            AnalysisImageSlot(
                run_id=run_id, slot_key=key, slot_kind=kind, status=SlotStatus.PENDING.value
            )
            for key, kind in slots.items()
            if key not in existing
        ),
    )


def record_auto_result(
    session: Session,
    run_id: uuid.UUID,
    slot_key: str,
    *,
    media_file_id: uuid.UUID | None,
    attempts: int,
    now: datetime,
) -> None:
    """Store the outcome of the automatic attempts: ready with the image, or not available."""
    slot = repositories.find_slot(session, run_id, slot_key, lock=True)
    assert slot is not None  # noqa: S101  (slots are created before they are filled)
    slot.status = SlotStatus.READY.value if media_file_id else SlotStatus.NOT_AVAILABLE_YET.value
    slot.media_file_id = media_file_id
    slot.auto_attempts = attempts
    slot.updated_at = now


def claim_manual_retry(
    session: Session, run_id: uuid.UUID, slot_key: str, *, limit: int, now: datetime
) -> bool:
    """Reserve one manual retry: only a "not available yet" slot with retries left qualifies.

    The slot row is locked, so two clicks never start two vendor calls. The retry is counted
    when it starts (a failed retry stays used) and the slot shows as generating meanwhile.
    """
    slot = repositories.find_slot(session, run_id, slot_key, lock=True)
    if (
        slot is None
        or slot.status != SlotStatus.NOT_AVAILABLE_YET.value
        or slot.manual_retries >= limit
    ):
        return False
    slot.manual_retries += 1
    slot.status = SlotStatus.PENDING.value
    slot.updated_at = now
    return True


def record_manual_result(
    session: Session,
    run_id: uuid.UUID,
    slot_key: str,
    *,
    media_file_id: uuid.UUID | None,
    now: datetime,
) -> None:
    """Store the outcome of a manual retry."""
    slot = repositories.find_slot(session, run_id, slot_key, lock=True)
    assert slot is not None  # noqa: S101
    slot.status = SlotStatus.READY.value if media_file_id else SlotStatus.NOT_AVAILABLE_YET.value
    slot.media_file_id = media_file_id
    slot.updated_at = now


@dataclass(frozen=True)
class ResultView:
    """A finished run's stored result, as the Report module reads it (contract C7, U8)."""

    run_id: uuid.UUID
    user_id: uuid.UUID
    result: dict[str, Any]
    published_at: datetime
    started_at: datetime
    completed_at: datetime | None
    front_file_id: uuid.UUID | None
    slots: tuple[SlotView, ...]


def latest_result_view(session: Session, user_id: uuid.UUID) -> ResultView | None:
    """The user's newest run's stored result, or ``None`` until one exists (no approval step)."""
    run = repositories.find_latest_run(session, user_id)
    if run is None:
        return None
    stored = repositories.find_result(session, run.id)
    if stored is None:
        return None
    return ResultView(
        run_id=run.id,
        user_id=run.user_id,
        result=dict(stored.result),
        published_at=stored.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        front_file_id=repositories.list_photos(session, run.id).get("front"),
        slots=tuple(_view(slot) for slot in repositories.list_slots(session, run.id)),
    )
