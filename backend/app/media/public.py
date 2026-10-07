"""The MediaStore module's public interface (contract C8). Other modules import only this.

- ``build_media_store``: the store with the FileStorage adapter chosen by ``MEDIA_BACKEND``.
- ``MediaStore`` (``put`` / ``get`` / ``retire`` / ``purge`` / ``discard``) and its refs.
- ``prepare_photo`` / ``decode_stored``: decode, normalise and re-encode on write.
- ``router``: ``GET /media/{fileId}`` (mounted as a protected route).
"""

from __future__ import annotations

from app.media.images import (
    PreparedImage,
    UnreadableImageError,
    UnsupportedImageTypeError,
    decode_stored,
    prepare_photo,
)
from app.media.models import MediaKind
from app.media.routes import router
from app.media.services import MediaStore, StoredFile, StoredFileRef
from app.media.storage import LocalDiskStorage, StorageError
from app.platform.clock import Clock
from app.platform.settings import Settings

__all__ = [
    "MediaKind",
    "MediaStore",
    "PreparedImage",
    "StorageError",
    "StoredFile",
    "StoredFileRef",
    "UnreadableImageError",
    "UnsupportedImageTypeError",
    "build_media_store",
    "decode_stored",
    "prepare_photo",
    "router",
]


def build_media_store(settings: Settings, *, clock: Clock) -> MediaStore:
    """The MediaStore for ``MEDIA_BACKEND`` (only ``local`` exists today; AC1.10.1)."""
    return MediaStore(storage=LocalDiskStorage(settings.media_root), clock=clock)
