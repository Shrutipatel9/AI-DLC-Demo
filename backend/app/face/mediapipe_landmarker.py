"""MediaPipe Face Landmarker adapter (AC1.11.1-AC1.11.3).

- The model is loaded once per process and shared (a module-level cache keyed by path);
  only the model object is cached, never a result ([IV] §5).
- The landmarker runs in IMAGE mode, which is deterministic: the same pixels give the same
  landmarks (AC1.11.3).
- Calls are serialised with a lock: one landmarker instance is not safe to call from
  several request threads at once.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np

from app.face.geometry import FaceFound, FaceResult, MultipleFaces, NoFace, RgbImage
from app.face.model import LANDMARK_COUNT, MODEL_SHA256, FaceModelError, verify_model

logger = logging.getLogger("face")

#: Ask for two faces so "more than one face" can be told apart from "one face".
_MAX_FACES = 2

_CACHE_LOCK = threading.Lock()
_LANDMARKERS: dict[tuple[str, str], tuple[Any, threading.Lock]] = {}


def _create_landmarker(path: Path) -> Any:
    # MediaPipe logs through glog/absl; keep its start-up chatter out of the app log.
    os.environ.setdefault("GLOG_minloglevel", "2")
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options

    options = vision.FaceLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(path)),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=_MAX_FACES,
        output_facial_transformation_matrixes=True,
    )
    return vision.FaceLandmarker.create_from_options(options)


def _shared_landmarker(path: Path, sha256: str) -> tuple[Any, threading.Lock]:
    key = (str(path.resolve()), sha256)
    with _CACHE_LOCK:
        cached = _LANDMARKERS.get(key)
        if cached is None:
            verify_model(path, sha256)
            cached = (_create_landmarker(path), threading.Lock())
            _LANDMARKERS[key] = cached
            logger.info("face model loaded", extra={"event": "face.model.loaded"})
        return cached


def yaw_from_matrix(matrix: Any) -> float:
    """Head yaw in degrees from MediaPipe's 4x4 face transformation matrix.

    Positive when the nose points to the image's right (see ``FaceFound.yaw_degrees``).
    """
    rotation = np.asarray(matrix, dtype=np.float64)
    return math.degrees(math.atan2(rotation[0, 2], rotation[2, 2]))


class MediaPipeFaceGeometry:
    """FaceGeometry backed by the pinned MediaPipe Face Landmarker model.

    Args:
        model_path: Path of the ``.task`` model file.
        model_sha256: The pinned hash the file must have.
    """

    def __init__(self, model_path: Path, model_sha256: str = MODEL_SHA256) -> None:
        self.model_path = model_path
        self.model_sha256 = model_sha256

    def load(self) -> None:
        """Load (or reuse) the process-wide model.

        Raises:
            FaceModelError: When the model file is missing or not the pinned version.
        """
        _shared_landmarker(self.model_path, self.model_sha256)

    def detect(self, image: RgbImage) -> FaceResult:
        """Run the landmarker on an RGB image.

        Raises:
            FaceModelError: When the model cannot be loaded.
            ValueError: When ``image`` is not an ``(h, w, 3)`` uint8 array.
        """
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError("FaceGeometry expects an (h, w, 3) uint8 RGB image")
        from mediapipe import Image, ImageFormat

        landmarker, lock = _shared_landmarker(self.model_path, self.model_sha256)
        frame = Image(image_format=ImageFormat.SRGB, data=np.ascontiguousarray(image))
        with lock:
            result = landmarker.detect(frame)
        faces = list(result.face_landmarks or [])
        if not faces:
            return NoFace()
        if len(faces) > 1:
            return MultipleFaces(count=len(faces))
        points = faces[0]
        if len(points) != LANDMARK_COUNT:  # pragma: no cover - a different model version
            raise FaceModelError(f"expected {LANDMARK_COUNT} landmarks, got {len(points)}")
        matrices = list(result.facial_transformation_matrixes or [])
        yaw = yaw_from_matrix(matrices[0]) if matrices else 0.0
        height, width = int(image.shape[0]), int(image.shape[1])
        return FaceFound(
            landmarks=tuple((float(p.x), float(p.y), float(p.z)) for p in points),
            width=width,
            height=height,
            yaw_degrees=yaw,
        )
