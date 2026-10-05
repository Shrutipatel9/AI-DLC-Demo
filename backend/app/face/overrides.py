"""Landmark overrides for test fixtures (development and test only).

[Decided by delivery team] MediaPipe pulls synthetic faces towards an average face, so no
licence-clean synthetic image of a "different person" scores above the 0.6 identity
threshold. The browser journey for a mismatched photo set therefore uses this wrapper:
for an image whose decoded pixels hash to an entry in the overrides file, it returns the
recorded landmarks instead of running the model; every other image goes to the real
MediaPipe model. Settings refuse an overrides file outside development and test.

File format (written by ``tools.make_face_fixtures``)::

    {"version": 1,
     "images": {"<pixel sha256>": {"landmarks": [[x, y, z], ...478], "yawDegrees": 0.0}}}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.face.geometry import FaceFound, FaceGeometry, FaceResult, RgbImage, pixel_hash
from app.face.model import LANDMARK_COUNT


class OverridesFileError(ValueError):
    """The overrides file is missing or malformed."""


def load_overrides(path: Path) -> dict[str, tuple[tuple[tuple[float, float, float], ...], float]]:
    """Read and validate an overrides file.

    Raises:
        OverridesFileError: When the file cannot be read or has the wrong shape.
    """
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OverridesFileError(f"cannot read face landmark overrides at {path}") from exc
    if not isinstance(data, dict):
        raise OverridesFileError("face landmark overrides must be a JSON object")
    images = data.get("images")
    if data.get("version") != 1 or not isinstance(images, dict):
        raise OverridesFileError("face landmark overrides must be {version: 1, images: {...}}")
    parsed: dict[str, tuple[tuple[tuple[float, float, float], ...], float]] = {}
    for key, entry in images.items():
        landmarks = entry.get("landmarks") if isinstance(entry, dict) else None
        if not isinstance(landmarks, list) or len(landmarks) != LANDMARK_COUNT:
            raise OverridesFileError(f"override {key[:12]} must have {LANDMARK_COUNT} landmarks")
        points = tuple((float(p[0]), float(p[1]), float(p[2])) for p in landmarks)
        parsed[key] = (points, float(entry.get("yawDegrees", 0.0)))
    return parsed


class OverrideFaceGeometry:
    """Recorded landmarks for known fixture images; the real model for everything else."""

    def __init__(self, inner: FaceGeometry, overrides_path: Path) -> None:
        self.inner = inner
        self.overrides = load_overrides(overrides_path)

    def load(self) -> None:
        """Load the wrapped model."""
        self.inner.load()

    def detect(self, image: RgbImage) -> FaceResult:
        """The recorded result for a known image, otherwise the wrapped model's."""
        entry = self.overrides.get(pixel_hash(image))
        if entry is None:
            return self.inner.detect(image)
        landmarks, yaw = entry
        return FaceFound(
            landmarks=landmarks,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            yaw_degrees=yaw,
        )
