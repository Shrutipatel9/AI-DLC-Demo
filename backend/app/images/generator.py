"""Generates one image: the vendor call, the checks and the private storage.

The ``ImageEditor`` port is the only vendor seam (NFR-013): which vendor and model run is
configuration. No database transaction is held across the vendor call.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from app.ai.public import (
    AiBadOutputError,
    AiError,
    AiRateLimitError,
    AiRequestRejectedError,
    ImageEditor,
    ImageInput,
)
from app.images.catalog import PromptSpec
from app.media.public import (
    MediaKind,
    MediaStore,
    StorageError,
    UnreadableImageError,
    decode_stored,
)
from app.platform.db import SessionFactory

logger = logging.getLogger("images")

#: A vendor ``retry_after`` hint is honoured up to this many seconds.
MAX_RATE_LIMIT_WAIT_SECONDS = 60.0

Sleeper = Callable[[float], None]


class SlotGenerator:
    """One image at a time.

    Args:
        editor: The configured image vendor adapter.
        media: Private storage for the result.
        session_factory: Short database sessions (storing the image).
        fidelity: The image-edit fidelity setting (AC9.1.2).
        auto_retries: Retries after the first attempt (AC9.5.1).
        backoff_seconds: Wait after a rate-limit answer without a hint.
        sleep: Waits (tests pass a recorder).
    """

    def __init__(
        self,
        *,
        editor: ImageEditor,
        media: MediaStore,
        session_factory: SessionFactory,
        fidelity: str,
        auto_retries: int,
        backoff_seconds: float,
        sleep: Sleeper = time.sleep,
    ) -> None:
        self.editor = editor
        self.media = media
        self.session_factory = session_factory
        self.fidelity = fidelity
        self.auto_retries = auto_retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep

    def attempt(self, user_id: uuid.UUID, source: ImageInput, spec: PromptSpec) -> uuid.UUID:
        """One vendor call; the checked image is stored privately for ``user_id``.

        Raises:
            AiError: A typed vendor failure, or a result that is not an image.
            StorageError: The image could not be stored.
        """
        data = self.editor.edit(source, spec.instruction, self.fidelity)
        try:
            decode_stored(data)
        except UnreadableImageError:
            raise AiBadOutputError(
                "The AI service returned something that is not an image."
            ) from None
        with self.session_factory() as session:
            ref = self.media.put(session, user_id, MediaKind.AI_IMAGE, data, "image/png")
            try:
                session.commit()
            except Exception:
                self.media.discard(ref)
                raise
        return ref.file_id

    def generate(
        self, user_id: uuid.UUID, source: ImageInput, spec: PromptSpec
    ) -> tuple[uuid.UUID | None, int]:
        """Try 1 + ``auto_retries`` times (AC9.5.1, AC9.5.2).

        Rate-limit answers back off (their hint, else the configured wait) and count as
        attempts (AC7.6.4). A request the vendor refuses is not retried.

        Returns:
            ``(file id or None, vendor calls made)``.
        """
        calls = 0
        for attempt in range(1 + self.auto_retries):
            calls += 1
            try:
                return self.attempt(user_id, source, spec), calls
            except AiRequestRejectedError:
                self._log_failure(spec, "rejected")
                break
            except AiRateLimitError as error:
                self._log_failure(spec, "rate_limited")
                if attempt < self.auto_retries:
                    hint = error.retry_after
                    wait = self.backoff_seconds if hint is None else hint
                    self.sleep(min(max(wait, 0.0), MAX_RATE_LIMIT_WAIT_SECONDS))
            except (AiError, StorageError) as error:
                self._log_failure(spec, type(error).__name__)
        return None, calls

    @staticmethod
    def _log_failure(spec: PromptSpec, reason: str) -> None:
        logger.warning(
            "image attempt failed",
            extra={"event": "images.attempt_failed", "slot": spec.slot_key, "reason": reason},
        )
