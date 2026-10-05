"""Face geometry results and the FaceGeometry port (AC1.11.1).

A detection returns exactly one of:

- :class:`FaceFound`: the 478 landmarks of the single face, plus the estimated head yaw;
- :class:`NoFace`: no face was found;
- :class:`MultipleFaces`: more than one face was found.

Landmarks are normalised (``x`` and ``y`` in 0..1 of the image width and height), exactly as
MediaPipe returns them. :meth:`FaceFound.points_px` converts them to pixels.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

#: An RGB image as a ``(height, width, 3)`` ``uint8`` array.
RgbImage = NDArray[np.uint8]

Landmark = tuple[float, float, float]


@dataclass(frozen=True)
class FaceFound:
    """Exactly one face.

    Attributes:
        landmarks: 478 normalised ``(x, y, z)`` points in MediaPipe's order.
        width: Image width in pixels.
        height: Image height in pixels.
        yaw_degrees: Head turn estimated from the face transformation matrix. Positive
            means the nose points to the image's right (the person turned to their own
            left, showing their right cheek); negative means the opposite.
    """

    landmarks: tuple[Landmark, ...]
    width: int
    height: int
    yaw_degrees: float

    def points_px(self) -> NDArray[np.float64]:
        """The landmarks in pixel coordinates, shape ``(478, 2)``."""
        points = np.asarray([(x, y) for x, y, _ in self.landmarks], dtype=np.float64)
        return points * np.asarray([self.width, self.height], dtype=np.float64)


@dataclass(frozen=True)
class NoFace:
    """No face was found."""


@dataclass(frozen=True)
class MultipleFaces:
    """More than one face was found."""

    count: int


FaceResult = FaceFound | NoFace | MultipleFaces


class FaceGeometry(Protocol):
    """Finds the face landmarks in an image. Results are never cached (AC1.11.2)."""

    def detect(self, image: RgbImage) -> FaceResult:
        """Detect the face in ``image``."""
        ...

    def load(self) -> None:
        """Load the model now (start-up), so a missing model fails fast."""
        ...


def pixel_hash(image: RgbImage) -> str:
    """SHA-256 of the decoded pixels and their shape (keys the landmark overrides)."""
    contiguous = np.ascontiguousarray(image, dtype=np.uint8)
    digest = hashlib.sha256(f"{contiguous.shape[0]}x{contiguous.shape[1]}:".encode())
    digest.update(contiguous.tobytes())
    return digest.hexdigest()
