"""PhotoIntake service: upload with per-photo checks, the photo set, the same-person check.

FR-005, FR-006, BR-004, BR-005; contract C4.

Plan decisions ([Decided by delivery team] unless noted):

- **Upload order.** Size and type are checked first (413 ``PHOTO_TOO_LARGE``, 415
  ``PHOTO_UNSUPPORTED_TYPE``); the photo is then decoded and re-encoded (metadata stripped,
  HEIC converted), the face is detected and the per-photo checks run, all before any row is
  locked.
- **Accepted** photos replace the angle's current photo; the old file is retired and deleted
  after the commit (AC1.10.3, AC5.2.4).
- **Rejected** uploads are never stored. If the angle already has an accepted photo it is
  kept unchanged (a bad retake does not destroy a good photo); otherwise the angle records
  ``rejected`` with its reasons, so a reload shows them. Either way the answer is 422
  ``PHOTO_REJECTED`` with one ``{angle, reason}`` per failed check.
- **Same-person check** (:meth:`PhotoIntakeService.evaluate_identity`): one function, run
  from the photos stored right now on every call, with nothing cached: each photo is read,
  decoded and measured again ([IV] §1, §5; AC5.6.5). ``GET /photos``, every accepted upload,
  and the C4 port for checkout (U5) and "Start Analysis" (U6) all call it. A stored photo in
  which no single face can be found any more is flagged for a retake.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.face.public import FaceFound, FaceGeometry
from app.media.public import (
    MediaKind,
    MediaStore,
    StoredFileRef,
    UnreadableImageError,
    UnsupportedImageTypeError,
    decode_stored,
    prepare_photo,
)
from app.photos import repositories
from app.photos.catalog import PhotoCatalog
from app.photos.checks import CheckThresholds, PhotoReason, check_photo
from app.photos.identity import IdentityResult, Signature, evaluate_signatures, signature
from app.photos.models import CaptureMethod, Photo, PhotoStatus
from app.platform.clock import Clock
from app.platform.errors import (
    NotFound,
    PhotoIdentityMismatch,
    PhotoRejected,
    PhotoSetIncomplete,
    PhotoTooLarge,
    PhotoUnsupportedType,
)

logger = logging.getLogger("photos")

PhotoState = Literal["missing", "accepted", "rejected"]
BYTES_PER_MB = 1024 * 1024


@dataclass(frozen=True)
class PhotoView:
    """One required angle's current state (C1 ``PhotoSet.photos[]``)."""

    angle: str
    status: PhotoState
    reasons: tuple[str, ...]
    file_id: uuid.UUID | None
    capture_method: str | None
    updated_at: datetime | None


@dataclass(frozen=True)
class PhotoSetView:
    """The required angles, each angle's photo and the fresh same-person result."""

    required_angles: tuple[str, ...]
    photos: tuple[PhotoView, ...]
    identity: IdentityResult

    @property
    def accepted_count(self) -> int:
        """How many required angles have an accepted photo ("2 of 3", AC5.2.6)."""
        return sum(1 for photo in self.photos if photo.status == "accepted")


@dataclass(frozen=True)
class PhotoSetState:
    """For the Journey (C4 ``set_state``)."""

    complete: bool
    consistent: bool


class PhotoIntakeService:
    """Photo use cases. Public methods that change data commit their own transaction.

    Args:
        catalog: The validated photo catalog (configured angles in order).
        media: The MediaStore.
        geometry: The shared FaceGeometry service.
        clock: Time source.
        thresholds: The per-photo check thresholds.
        identity_threshold: The same-person threshold (``IDENTITY_THRESHOLD``).
        max_upload_bytes: The upload limit (``PHOTO_MAX_UPLOAD_BYTES``).
        max_dimension: Longest stored side in pixels (``PHOTO_MAX_DIMENSION``).
    """

    def __init__(
        self,
        *,
        catalog: PhotoCatalog,
        media: MediaStore,
        geometry: FaceGeometry,
        clock: Clock,
        thresholds: CheckThresholds,
        identity_threshold: float,
        max_upload_bytes: int,
        max_dimension: int,
    ) -> None:
        self.catalog = catalog
        self.media = media
        self.geometry = geometry
        self.clock = clock
        self.thresholds = thresholds
        self.identity_threshold = identity_threshold
        self.max_upload_bytes = max_upload_bytes
        self.max_dimension = max_dimension

    # --- Reading -------------------------------------------------------------------------

    def _current(self, session: Session, user_id: uuid.UUID) -> dict[str, Photo]:
        configured = set(self.catalog.angle_ids)
        return {
            photo.angle: photo
            for photo in repositories.find_all(session, user_id)
            if photo.angle in configured
        }

    def photo_set(self, session: Session, user_id: uuid.UUID) -> PhotoSetView:
        """Every required angle's state and a freshly computed same-person result."""
        rows = self._current(session, user_id)
        views: list[PhotoView] = []
        for angle in self.catalog.angle_ids:
            row = rows.get(angle)
            if row is None:
                views.append(PhotoView(angle, "missing", (), None, None, None))
                continue
            status: PhotoState = "accepted" if row.status == PhotoStatus.ACCEPTED else "rejected"
            views.append(
                PhotoView(
                    angle=angle,
                    status=status,
                    reasons=tuple(str(reason) for reason in row.reasons),
                    file_id=row.media_file_id,
                    capture_method=row.capture_method,
                    updated_at=row.updated_at,
                )
            )
        return PhotoSetView(
            required_angles=tuple(self.catalog.angle_ids),
            photos=tuple(views),
            identity=self._identity(session, user_id, rows),
        )

    # --- The same-person check (C4) ----------------------------------------------------------

    def _identity(
        self, session: Session, user_id: uuid.UUID, rows: dict[str, Photo]
    ) -> IdentityResult:
        accepted = {
            angle: row.media_file_id
            for angle, row in rows.items()
            if row.status == PhotoStatus.ACCEPTED and row.media_file_id is not None
        }
        if any(angle not in accepted for angle in self.catalog.angle_ids):
            return IdentityResult(status="incomplete", mismatched_angles=())
        signatures: dict[str, Signature] = {}
        unmeasurable: list[str] = []
        for angle in self.catalog.angle_ids:
            file_id = accepted[angle]
            assert file_id is not None  # noqa: S101  (narrowed by the comprehension above)
            try:
                stored = self.media.get(session, file_id, user_id)
                face = self.geometry.detect(decode_stored(stored.data))
            except (NotFound, UnreadableImageError):
                # The stored file is gone or damaged: flag the angle for a retake.
                unmeasurable.append(angle)
                continue
            if isinstance(face, FaceFound):
                try:
                    signatures[angle] = signature(face)
                    continue
                except ValueError:
                    pass
            unmeasurable.append(angle)
        if unmeasurable:
            logger.warning(
                "stored photo could not be measured",
                extra={"event": "photos.identity.unmeasurable", "angles": unmeasurable},
            )
            return IdentityResult(status="mismatch", mismatched_angles=tuple(unmeasurable))
        return evaluate_signatures(self.catalog.angle_ids, signatures, self.identity_threshold)

    def evaluate_identity(self, session: Session, user_id: uuid.UUID) -> IdentityResult:
        """The same-person result from the photos stored now; never cached (AC5.6.5)."""
        return self._identity(session, user_id, self._current(session, user_id))

    def snapshot_for_run(self, session: Session, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
        """``angle -> file id`` of a complete, consistent set (C4 ``snapshot_for_run``).

        Raises:
            PhotoSetIncomplete: 409 when a required angle has no accepted photo.
            PhotoIdentityMismatch: 409 naming the flagged angles (BR-005).
        """
        rows = self._current(session, user_id)
        result = self._identity(session, user_id, rows)
        if result.status == "incomplete":
            raise PhotoSetIncomplete()
        if result.status == "mismatch":
            raise PhotoIdentityMismatch(result.mismatched_angles)
        snapshot: dict[str, uuid.UUID] = {}
        for angle in self.catalog.angle_ids:
            file_id = rows[angle].media_file_id
            assert file_id is not None  # noqa: S101  (a consistent set is fully accepted)
            snapshot[angle] = file_id
        return snapshot

    def set_state(self, session: Session, user_id: uuid.UUID) -> PhotoSetState:
        """Complete and consistent flags for the Journey (C4 ``set_state``)."""
        result = self.evaluate_identity(session, user_id)
        return PhotoSetState(
            complete=result.status != "incomplete", consistent=result.status == "consistent"
        )

    # --- Upload ------------------------------------------------------------------------------

    def upload(
        self,
        session: Session,
        user_id: uuid.UUID,
        angle: str,
        data: bytes,
        capture_method: Literal["upload", "camera"] | None,
    ) -> PhotoSetView:
        """Check one photo and, when accepted, make it the angle's current photo.

        Raises:
            NotFound: For an angle that is not configured.
            PhotoTooLarge: 413 over ``PHOTO_MAX_UPLOAD_BYTES``.
            PhotoUnsupportedType: 415 for anything but JPEG, PNG or HEIC.
            PhotoRejected: 422 with the failed checks (``UNREADABLE`` for a broken file).
            app.media.public.StorageError: When the file cannot be stored.
        """
        spec = self.catalog.angle(angle)
        if spec is None:
            raise NotFound("We couldn't find that photo step.")
        if len(data) > self.max_upload_bytes:
            limit = max(1, self.max_upload_bytes // BYTES_PER_MB)
            raise PhotoTooLarge(
                f"This photo is larger than {limit} MB. Please choose a smaller photo."
            )
        try:
            prepared = prepare_photo(data, max_dimension=self.max_dimension)
        except UnsupportedImageTypeError:
            raise PhotoUnsupportedType() from None
        except UnreadableImageError:
            self._record_rejection(session, user_id, angle, [PhotoReason.UNREADABLE])
            raise PhotoRejected(angle, [PhotoReason.UNREADABLE.value]) from None

        face = self.geometry.detect(prepared.pixels)
        reasons = check_photo(prepared.pixels, face, spec, self.thresholds)
        if reasons:
            self._record_rejection(session, user_id, angle, reasons)
            raise PhotoRejected(angle, [reason.value for reason in reasons])

        ref = self.media.put(
            session, user_id, MediaKind.PHOTO, prepared.encoded, prepared.content_type
        )
        retired: list[str] = []
        try:
            row = repositories.lock_photo(session, user_id, angle, self.clock.now())
            previous = row.media_file_id
            row.status = PhotoStatus.ACCEPTED.value
            row.media_file_id = ref.file_id
            row.reasons = []
            row.capture_method = (
                CaptureMethod(capture_method).value if capture_method is not None else None
            )
            row.updated_at = self.clock.now()
            session.flush()
            if previous is not None:
                key = self.media.retire(session, previous)
                if key is not None:
                    retired.append(key)
            session.commit()
        except Exception:
            session.rollback()
            self._discard(ref)
            raise
        self.media.purge(retired)
        logger.info(
            "photo accepted",
            extra={"event": "photos.photo.accepted", "userId": str(user_id), "angle": angle},
        )
        return self.photo_set(session, user_id)

    def _discard(self, ref: StoredFileRef) -> None:
        self.media.discard(ref)

    def _record_rejection(
        self, session: Session, user_id: uuid.UUID, angle: str, reasons: list[PhotoReason]
    ) -> None:
        """Keep an accepted photo; otherwise remember the reasons (commits)."""
        row = repositories.lock_photo(session, user_id, angle, self.clock.now())
        if row.status != PhotoStatus.ACCEPTED:
            row.status = PhotoStatus.REJECTED.value
            row.reasons = [reason.value for reason in reasons]
            row.updated_at = self.clock.now()
        session.commit()
        logger.info(
            "photo rejected",
            extra={
                "event": "photos.photo.rejected",
                "userId": str(user_id),
                "angle": angle,
                "reasons": [reason.value for reason in reasons],
            },
        )
