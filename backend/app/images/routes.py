"""Image HTTP routes (US9.1-US9.5): owner-only, ``Cache-Control: no-store``.

Mounted with ``current_user``. Handlers stay thin and call :class:`ImageGenerationService`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.images.dependencies import get_images, no_store
from app.images.schemas import ImageSlotOut, ImagesOut, to_out, to_slot_out
from app.images.service import ImageGenerationService
from app.platform.db import get_session
from app.platform.errors import error_responses

SessionDep = Annotated[Session, Depends(get_session)]
ImagesDep = Annotated[ImageGenerationService, Depends(get_images)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]

router = APIRouter(tags=["images"], dependencies=[Depends(no_store)])


@router.get(
    "/images",
    response_model=ImagesOut,
    response_model_by_alias=True,
    responses=error_responses(401, 404),
    summary="The run's AI images and their state (polled while generating)",
)
def get_images_state(user: UserDep, session: SessionDep, images: ImagesDep) -> ImagesOut:
    """Slots in report order: ready (with an owner-checked URL), generating or not available."""
    return to_out(images.state_for(session, user.user_id))


@router.post(
    "/images/{slotId}/retry",
    response_model=ImageSlotOut,
    response_model_by_alias=True,
    responses=error_responses(401, 404, 409),
    summary="Retry one image that is not available yet (at most 3 times per image)",
)
def post_retry(
    slot_id: Annotated[str, Path(alias="slotId", max_length=32)],
    user: UserDep,
    session: SessionDep,
    images: ImagesDep,
) -> ImageSlotOut:
    """One attempt. 409 ``IMAGE_RETRY_NOT_AVAILABLE`` past the limit, with no vendor call."""
    return to_slot_out(images.retry(session, user.user_id, slot_id))
