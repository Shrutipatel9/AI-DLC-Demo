"""Response models for ``/images`` (camelCase JSON).

Additive to contract C1 [Decided by delivery team]: the ``/images`` routes are our own shape
(the contract names the screen, not the wire form). Images are served by the existing
owner-checked ``/media/{fileId}`` route.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.images.catalog import AI_LABEL
from app.images.service import ImagesState, SlotState


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ImageSlotOut(CamelModel):
    """One image slot."""

    slot_id: str
    group: Literal["feature", "hairstyle", "outfit", "aging"]
    title: str
    status: Literal["generating", "ready", "not_available"]
    image_url: str | None = None
    ai_label: str
    retries_left: int


class ImagesOut(CamelModel):
    """The run's images, in report order."""

    run_id: uuid.UUID
    generating: bool
    front_photo_url: str | None = None
    slots: list[ImageSlotOut]


def _slot(slot: SlotState) -> ImageSlotOut:
    return ImageSlotOut(
        slot_id=slot.slot_id,
        group=slot.group,
        title=slot.title,
        status=slot.state,
        image_url=None if slot.file_id is None else f"/media/{slot.file_id}",
        ai_label=AI_LABEL,
        retries_left=slot.retries_left,
    )


def to_slot_out(slot: SlotState) -> ImageSlotOut:
    """The wire form of one slot."""
    return _slot(slot)


def to_out(state: ImagesState) -> ImagesOut:
    """The wire form of the run's images."""
    return ImagesOut(
        run_id=state.run_id,
        generating=state.generating,
        front_photo_url=None if state.front_file_id is None else f"/media/{state.front_file_id}",
        slots=[_slot(slot) for slot in state.slots],
    )
