"""The pinned Face Landmarker model (AC1.11.2).

The model file is not committed. ``uv run python -m tools.fetch_face_model`` downloads it to
``FACE_MODEL_PATH`` (default ``var/models/face_landmarker.task``, git-ignored) and checks the
SHA-256 below. The app refuses a file whose hash differs, so every environment runs exactly
the same model version.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Model family and version, as published by MediaPipe.
MODEL_VERSION = "face_landmarker/float16/1"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/"
    "float16/1/face_landmarker.task"
)
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"

#: The face mesh has 468 points plus 10 iris points.
LANDMARK_COUNT = 478

_CHUNK = 1024 * 1024


class FaceModelError(RuntimeError):
    """The model file is missing or is not the pinned version."""


def file_sha256(path: Path) -> str:
    """Hex SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model(path: Path, expected_sha256: str = MODEL_SHA256) -> None:
    """Check that ``path`` is the pinned model.

    Raises:
        FaceModelError: When the file is missing or its hash differs.
    """
    if not path.is_file():
        raise FaceModelError(
            f"Face Landmarker model not found at {path}. "
            "Run `uv run python -m tools.fetch_face_model` (see backend/README.md)."
        )
    actual = file_sha256(path)
    if actual != expected_sha256:
        raise FaceModelError(
            f"Face Landmarker model at {path} is not the pinned version {MODEL_VERSION} "
            "(SHA-256 mismatch). Run `uv run python -m tools.fetch_face_model` again."
        )
