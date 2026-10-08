"""MediaStore service (contract C8: ``put``, ``get``, ``retire``).

Transactions: ``put`` writes the bytes first and stages the database row; the caller
commits. When the caller's transaction fails it calls :meth:`MediaStore.discard`, so no
unreferenced file stays on disk. ``retire`` removes the row and returns the storage key;
the caller deletes the bytes with :meth:`MediaStore.purge` after its commit succeeds, so a
failed commit never leaves a row without a file.

A retired photo is deleted at once unless another module still references it: modules
register a reference check with :meth:`MediaStore.add_reference_check` (the analysis module
does, because a run keeps the photo files it started with, R-02). A referenced file is kept, row
and bytes, so the run can still read it (AC1.10.3; C8 "deleted when unreferenced").
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.media import repositories
from app.media.models import MediaFile, MediaKind
from app.media.storage import FileNotStoredError, FileStorage, StorageError
from app.platform.clock import Clock
from app.platform.errors import NotFound

logger = logging.getLogger("media")

#: ``(session, file id) -> bool``: does another module still need this file?
ReferenceCheck = Callable[[Session, uuid.UUID], bool]

_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}


@dataclass(frozen=True)
class StoredFileRef:
    """A file written by :meth:`MediaStore.put` (C8 ``StoredFileRef``)."""

    file_id: uuid.UUID
    content_type: str
    storage_key: str


@dataclass(frozen=True)
class StoredFile:
    """A file's bytes and content type, read for its owner."""

    file_id: uuid.UUID
    content_type: str
    data: bytes


class MediaStore:
    """Private file storage with owner checks.

    Args:
        storage: The FileStorage adapter selected by ``MEDIA_BACKEND``.
        clock: Time source.
    """

    def __init__(self, *, storage: FileStorage, clock: Clock) -> None:
        self.storage = storage
        self.clock = clock
        self._reference_checks: list[ReferenceCheck] = []

    def add_reference_check(self, check: ReferenceCheck) -> None:
        """Keep retired files that ``check`` says are still referenced."""
        self._reference_checks.append(check)

    def put(
        self,
        session: Session,
        owner_user_id: uuid.UUID,
        kind: MediaKind,
        data: bytes,
        content_type: str,
    ) -> StoredFileRef:
        """Store already re-encoded bytes (see ``prepare_photo``) and stage the row.

        Raises:
            ValueError: For a content type the store does not keep.
            StorageError: When the bytes cannot be written.
        """
        extension = _EXTENSIONS.get(content_type)
        if extension is None:
            raise ValueError(f"unsupported stored content type {content_type!r}")
        file_id = uuid.uuid4()
        key = f"{owner_user_id}/{file_id}.{extension}"
        self.storage.write(key, data)
        repositories.add(
            session,
            MediaFile(
                id=file_id,
                owner_user_id=owner_user_id,
                kind=kind.value,
                content_type=content_type,
                storage_key=key,
                size_bytes=len(data),
                created_at=self.clock.now(),
            ),
        )
        return StoredFileRef(file_id=file_id, content_type=content_type, storage_key=key)

    def discard(self, ref: StoredFileRef) -> None:
        """Delete the bytes of a ``put`` whose transaction did not commit."""
        self.purge([ref.storage_key])

    def get(self, session: Session, file_id: uuid.UUID, requester_user_id: uuid.UUID) -> StoredFile:
        """The file's bytes for its owner (AC1.10.2).

        Raises:
            NotFound: When the file is missing, owned by someone else, or its bytes are gone
                (never 403, so another user's file is indistinguishable from none).
            StorageError: When the storage backend fails.
        """
        record = repositories.find_owned(session, file_id, requester_user_id)
        if record is None:
            raise NotFound("We couldn't find that file.")
        try:
            data = self.storage.read(record.storage_key)
        except FileNotStoredError:
            logger.error(
                "stored file missing",
                extra={"event": "media.file.missing", "fileId": str(file_id)},
            )
            raise NotFound("We couldn't find that file.") from None
        return StoredFile(file_id=record.id, content_type=record.content_type, data=data)

    def retire(self, session: Session, file_id: uuid.UUID) -> str | None:
        """Remove a replaced file's row; returns its key for :meth:`purge` after commit.

        Returns ``None`` (and keeps the file) when it is missing or still referenced.
        """
        record = repositories.find(session, file_id)
        if record is None:
            return None
        if any(check(session, file_id) for check in self._reference_checks):
            return None
        key = record.storage_key
        repositories.remove(session, file_id)
        return key

    def purge(self, keys: Iterable[str]) -> None:
        """Delete stored bytes.

        A failure is logged (the file is orphaned), never raised, because the database change it
        follows has already committed.
        """
        for key in keys:
            try:
                self.storage.delete(key)
            except StorageError:
                logger.error("stored file not deleted", extra={"event": "media.file.orphaned"})
