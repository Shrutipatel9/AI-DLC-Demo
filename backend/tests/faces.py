"""Face fixture images shared by the face, media and photo tests (no fixtures here).

The PNGs under ``tests/fixtures/faces`` are synthetic renders of MediaPipe's canonical face
mesh (``tools.make_face_fixtures``); no real person's photo is committed. The one real face,
MediaPipe's published sample portrait, is downloaded with the model by
``uv run python -m tools.fetch_face_model`` (unit-test instructions, Setup).
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.face.public import RgbImage

BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND_DIR / "tests" / "fixtures" / "faces"
MODEL_PATH = BACKEND_DIR / "var" / "models" / "face_landmarker.task"
PORTRAIT_PATH = BACKEND_DIR / "var" / "models" / "portrait.jpg"
OVERRIDES_PATH = FIXTURES / "overrides.json"

A_FRONT = "person-a-front.png"
A_LEFT = "person-a-left.png"
A_RIGHT = "person-a-right.png"
B_LEFT = "person-b-left.png"
NO_FACE = "no-face.png"


def require_downloads() -> None:
    """Fail (never skip) with the fix when the pinned model or portrait is missing."""
    for path in (MODEL_PATH, PORTRAIT_PATH):
        if not path.is_file():
            pytest.fail(
                f"{path.name} is missing. Run `uv run python -m tools.fetch_face_model` "
                "in backend/ first (unit-test instructions, Setup).",
                pytrace=False,
            )


def fixture_bytes(name: str) -> bytes:
    """The committed fixture file's bytes."""
    return (FIXTURES / name).read_bytes()


def fixture_pixels(name: str) -> RgbImage:
    """The committed fixture decoded to RGB."""
    with Image.open(FIXTURES / name) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def portrait_pixels() -> RgbImage:
    """MediaPipe's sample portrait (one real face) decoded to RGB."""
    require_downloads()
    with Image.open(PORTRAIT_PATH) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def encode(pixels: RgbImage, image_format: str = "PNG", **options: object) -> bytes:
    """Encode pixels as an image file."""
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format=image_format, **options)
    return buffer.getvalue()
