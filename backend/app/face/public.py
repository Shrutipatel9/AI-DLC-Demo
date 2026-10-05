"""The FaceGeometry module's public interface. Other modules import only this.

- ``build_face_geometry``: the configured landmark service (MediaPipe, optionally wrapped by
  the development/test landmark overrides).
- The result types ``FaceFound`` / ``NoFace`` / ``MultipleFaces`` and ``RgbImage``.
"""

from __future__ import annotations

from app.face.geometry import (
    FaceFound,
    FaceGeometry,
    FaceResult,
    MultipleFaces,
    NoFace,
    RgbImage,
    pixel_hash,
)
from app.face.mediapipe_landmarker import MediaPipeFaceGeometry
from app.face.model import MODEL_SHA256, MODEL_URL, MODEL_VERSION, FaceModelError
from app.face.overrides import OverrideFaceGeometry
from app.platform.settings import Settings

__all__ = [
    "MODEL_SHA256",
    "MODEL_URL",
    "MODEL_VERSION",
    "FaceFound",
    "FaceGeometry",
    "FaceModelError",
    "FaceResult",
    "MediaPipeFaceGeometry",
    "MultipleFaces",
    "NoFace",
    "RgbImage",
    "build_face_geometry",
    "pixel_hash",
]


def build_face_geometry(settings: Settings) -> FaceGeometry:
    """The landmark service selected by configuration.

    Raises:
        app.face.overrides.OverridesFileError: When the overrides file is invalid.
    """
    geometry: FaceGeometry = MediaPipeFaceGeometry(settings.face_model_path)
    if settings.face_landmark_overrides_file is not None:
        geometry = OverrideFaceGeometry(geometry, settings.face_landmark_overrides_file)
    return geometry
