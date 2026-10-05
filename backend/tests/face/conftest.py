"""FaceGeometry fixtures: the real pinned MediaPipe model (loaded once per process)."""

from __future__ import annotations

import pytest

from app.face.public import FaceGeometry, MediaPipeFaceGeometry
from tests.faces import MODEL_PATH, require_downloads


@pytest.fixture(scope="session")
def face_geometry() -> FaceGeometry:
    """The real Face Landmarker (unit-test instructions: real MediaPipe in backend tests)."""
    require_downloads()
    geometry = MediaPipeFaceGeometry(MODEL_PATH)
    geometry.load()
    return geometry
