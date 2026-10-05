"""Photo HTTP routes (contract C1 ``/photos``; US5.1, US5.2, US5.5, US5.6, US5.10, US5.11).

Every route is protected (the app factory mounts this router with ``current_user``), sends
``Cache-Control: no-store`` and needs a submitted questionnaire (409
``QUESTIONNAIRE_NOT_SUBMITTED``). A user only ever reads and writes their own photos.
Handlers stay thin and call :class:`PhotoIntakeService`; they never touch repositories or
models. Photo files are read through ``GET /media/{fileId}`` (owner-checked).
"""

from __future__ import annotations

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, File, Form, Path, UploadFile
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.photos.catalog import PhotoCatalog
from app.photos.dependencies import get_photos, no_store, questionnaire_submitted
from app.photos.schemas import (
    AngleOut,
    IdentityOut,
    PhotoOut,
    PhotoRequirements,
    PhotoRuleOut,
    PhotoSet,
)
from app.photos.services import PhotoIntakeService, PhotoSetView
from app.platform.db import get_session
from app.platform.errors import error_responses

SessionDep = Annotated[Session, Depends(get_session)]
PhotosDep = Annotated[PhotoIntakeService, Depends(get_photos)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
AnglePath = Annotated[str, Path(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")]

ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/heic"]
CaptureMethodName = Literal["upload", "camera"]

router = APIRouter(
    tags=["photos"], dependencies=[Depends(no_store), Depends(questionnaire_submitted)]
)


def photo_set_out(view: PhotoSetView) -> PhotoSet:
    """Map the service view to the C1 PhotoSet."""
    return PhotoSet(
        required_angles=list(view.required_angles),
        accepted_count=view.accepted_count,
        photos=[
            PhotoOut(
                angle=photo.angle,
                status=photo.status,
                reasons=list(photo.reasons) if photo.status == "rejected" else [],
                image_url=f"/media/{photo.file_id}" if photo.file_id is not None else None,
                capture_method=cast(CaptureMethodName | None, photo.capture_method),  # DB-checked
                updated_at=photo.updated_at,
            )
            for photo in view.photos
        ],
        identity=IdentityOut(
            status=view.identity.status,
            mismatched_angles=list(view.identity.mismatched_angles),
        ),
    )


def requirements_out(catalog: PhotoCatalog, max_upload_bytes: int) -> PhotoRequirements:
    """Map the catalog to the requirements document."""
    return PhotoRequirements(
        catalog_version=catalog.version,
        rules=[PhotoRuleOut(id=rule.id, text=rule.text) for rule in catalog.rules],
        guidance=list(catalog.guidance),
        angles=[
            AngleOut(
                id=angle.id,
                label=angle.label,
                instruction=angle.instruction,
                turn_hint=angle.turn_hint,
                illustration=angle.illustration,
            )
            for angle in catalog.angles
        ],
        max_upload_bytes=max_upload_bytes,
        accepted_types=ACCEPTED_TYPES,
    )


@router.get(
    "/photos/requirements",
    response_model=PhotoRequirements,
    response_model_by_alias=True,
    responses=error_responses(401, 409),
    summary="The photo rules, capture guidance and the configured angles, in order (FR-005)",
)
def get_requirements(photos: PhotosDep) -> PhotoRequirements:
    """Return the rules and the configured angles (US5.1, AC5.2.1)."""
    return requirements_out(photos.catalog, photos.max_upload_bytes)


@router.get(
    "/photos",
    response_model=PhotoSet,
    response_model_by_alias=True,
    responses=error_responses(401, 409),
    summary="Required angles, each photo's status, and a freshly computed same-person result",
)
def get_photo_set(user: UserDep, session: SessionDep, photos: PhotosDep) -> PhotoSet:
    """Return the set; the same-person result is recomputed on every call (AC5.6.5)."""
    return photo_set_out(photos.photo_set(session, user.user_id))


@router.put(
    "/photos/{angle}",
    response_model=PhotoSet,
    response_model_by_alias=True,
    responses=error_responses(401, 404, 409, 413, 415, 422),
    summary="Uploads or replaces the photo for one angle; runs the per-photo checks",
)
def put_photo(
    angle: AnglePath,
    file: Annotated[UploadFile, File(description="JPEG, PNG or HEIC, up to 10 MB")],
    user: UserDep,
    session: SessionDep,
    photos: PhotosDep,
    capture_method: Annotated[
        Literal["upload", "camera"] | None, Form(alias="captureMethod")
    ] = None,
) -> PhotoSet:
    """Check and store one photo; 413/415/422 explain a refusal (AC5.2.3, US5.5, US5.10)."""
    # Read at most one byte past the limit: enough to know it is too large.
    data = file.file.read(photos.max_upload_bytes + 1)
    return photo_set_out(photos.upload(session, user.user_id, angle, data, capture_method))
