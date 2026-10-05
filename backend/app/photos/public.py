"""The PhotoIntake module's public interface (contract C4). Other modules import only this.

- ``build_photos``: wires the service from settings (used by the app factory). It loads and
  validates the photo catalog and the configured angles, so bad configuration fails start-up.
- ``router``: the ``/photos/*`` routes (mounted as protected routes).
- ``check_identity``: the same-person result from the photos stored now, never cached
  (C4 ``check_identity``; AC5.6.5). Checkout (U5) and "Start Analysis" (U6) call it.
- ``snapshot_for_run``: ``angle -> file id`` of a consistent set, or 409
  ``PHOTO_SET_INCOMPLETE`` / ``PHOTO_IDENTITY_MISMATCH`` (C4).
- ``get_photo_set_state``: complete/consistent flags for the Journey (C4 ``set_state``).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.face.public import FaceGeometry
from app.media.public import MediaStore
from app.photos.catalog import DEFAULT_CATALOG_FILE, load_catalog
from app.photos.checks import CheckThresholds
from app.photos.identity import IdentityResult
from app.photos.routes import router
from app.photos.services import PhotoIntakeService, PhotoSetState
from app.platform.clock import Clock
from app.platform.settings import Settings

__all__ = [
    "IdentityResult",
    "PhotoIntakeService",
    "PhotoSetState",
    "build_photos",
    "check_identity",
    "get_photo_set_state",
    "router",
    "snapshot_for_run",
]


def build_photos(
    settings: Settings, *, clock: Clock, media: MediaStore, geometry: FaceGeometry
) -> PhotoIntakeService:
    """Create the PhotoIntake service from settings.

    Raises:
        app.photos.catalog.CatalogError: When the catalog or ``PHOTO_ANGLES`` is invalid.
    """
    catalog = load_catalog(
        settings.photo_catalog_file or DEFAULT_CATALOG_FILE,
        settings.photo_angles,
        settings.yaw_range_overrides(),
    )
    return PhotoIntakeService(
        catalog=catalog,
        media=media,
        geometry=geometry,
        clock=clock,
        thresholds=CheckThresholds.from_settings(settings),
        identity_threshold=settings.identity_threshold,
        max_upload_bytes=settings.photo_max_upload_bytes,
        max_dimension=settings.photo_max_dimension,
    )


def check_identity(
    service: PhotoIntakeService, session: Session, user_id: uuid.UUID
) -> IdentityResult:
    """The same-person result for the user's current photos (C4 ``check_identity``)."""
    return service.evaluate_identity(session, user_id)


def snapshot_for_run(
    service: PhotoIntakeService, session: Session, user_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """The consistent set's file ids by angle (C4 ``snapshot_for_run``).

    Raises:
        app.platform.errors.PhotoSetIncomplete: When an angle has no accepted photo.
        app.platform.errors.PhotoIdentityMismatch: When the same-person check fails.
    """
    return service.snapshot_for_run(session, user_id)


def get_photo_set_state(
    service: PhotoIntakeService, session: Session, user_id: uuid.UUID
) -> PhotoSetState:
    """Complete and consistent flags (C4 ``set_state``)."""
    return service.set_state(session, user_id)
