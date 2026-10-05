"""Per-photo checks (US5.5, US5.10; FR-006, BR-005, ASM-002).

Each check that fails adds one reason code; the browser turns a code into a photo-focused
message and a fix hint, never a comment on the person's appearance (AC5.5.4). Every
threshold comes from configuration (AC5.5.3); the initial values were set during
development against the fixtures and MediaPipe's sample portrait (ASM-002, US5.9).

Checks, in order:

1. minimum resolution (``TOO_SMALL``);
2. exactly one face (``NO_FACE`` / ``MULTIPLE_FACES``); without a face the remaining
   checks cannot run (a dark photo without a face also gets ``TOO_DARK``);
3. brightness of the face region (``TOO_DARK`` / ``TOO_BRIGHT``);
4. face-to-frame proportion: the landmark box's share of the image area
   (``FACE_TOO_SMALL`` / ``FACE_TOO_LARGE``);
5. pose matches the angle: the head yaw must be inside the angle's range
   (``POSE_MISMATCH``);
6. covered eyes or mouth ([Assumption] first-pass heuristic, AC5.10.2): compared with the
   cheeks, the region is much darker (dark glasses, a hat's shadow) or almost flat (a hand,
   a mask) (``EYES_COVERED`` / ``MOUTH_COVERED``).

An unreadable file never gets here: decoding fails first (``UNREADABLE``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from app.face.public import FaceFound, FaceResult, MultipleFaces, NoFace, RgbImage
from app.photos.catalog import AngleSpec
from app.platform.settings import Settings


class PhotoReason(StrEnum):
    """Why a photo was rejected (``details[].reason`` of ``PHOTO_REJECTED``)."""

    UNREADABLE = "UNREADABLE"
    TOO_SMALL = "TOO_SMALL"
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    TOO_DARK = "TOO_DARK"
    TOO_BRIGHT = "TOO_BRIGHT"
    FACE_TOO_SMALL = "FACE_TOO_SMALL"
    FACE_TOO_LARGE = "FACE_TOO_LARGE"
    POSE_MISMATCH = "POSE_MISMATCH"
    EYES_COVERED = "EYES_COVERED"
    MOUTH_COVERED = "MOUTH_COVERED"


@dataclass(frozen=True)
class CheckThresholds:
    """The configured per-photo thresholds (``PHOTO_*`` settings)."""

    min_width: int
    min_height: int
    min_brightness: float
    max_brightness: float
    min_face_fraction: float
    max_face_fraction: float
    occlusion_dark_ratio: float
    occlusion_min_contrast: float

    @classmethod
    def from_settings(cls, settings: Settings) -> CheckThresholds:
        """Read the thresholds from settings."""
        return cls(
            min_width=settings.photo_min_width,
            min_height=settings.photo_min_height,
            min_brightness=settings.photo_min_brightness,
            max_brightness=settings.photo_max_brightness,
            min_face_fraction=settings.photo_min_face_fraction,
            max_face_fraction=settings.photo_max_face_fraction,
            occlusion_dark_ratio=settings.photo_occlusion_dark_ratio,
            occlusion_min_contrast=settings.photo_occlusion_min_contrast,
        )


# MediaPipe face mesh indices: eye contours, outer lip contour and two cheek points.
_EYES = (
    (33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246),
    (362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398),
)
_MOUTH = (61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185)
_CHEEKS = (205, 425)
_EYE_CENTRES = ((33, 133), (362, 263))
#: Region padding and cheek sample size, as fractions of the inter-eye distance.
_PAD = 0.05
_CHEEK_RADIUS = 0.12
_MIN_REGION_PIXELS = 4

Luminance = NDArray[np.float32]


def luminance(pixels: RgbImage) -> Luminance:
    """Rec. 601 luma (0-255) of an RGB image."""
    rgb = pixels.astype(np.float32)
    weights = np.asarray([0.299, 0.587, 0.114], dtype=np.float32)
    result: Luminance = rgb @ weights
    return result


def _box(gray: Luminance, x0: float, y0: float, x1: float, y1: float) -> NDArray[np.float32] | None:
    height, width = gray.shape
    left, top = max(0, int(np.floor(x0))), max(0, int(np.floor(y0)))
    right, bottom = min(width, int(np.ceil(x1)) + 1), min(height, int(np.ceil(y1)) + 1)
    if right <= left or bottom <= top:
        return None
    region = gray[top:bottom, left:right].ravel()
    return region if region.size >= _MIN_REGION_PIXELS else None


def _covered(region: NDArray[np.float32] | None, cheek: float, limits: CheckThresholds) -> bool:
    if region is None:
        return False
    darker = float(region.mean()) / cheek < limits.occlusion_dark_ratio
    flat = float(region.std()) / cheek < limits.occlusion_min_contrast
    return darker or flat


def _occlusion(gray: Luminance, face: FaceFound, limits: CheckThresholds) -> list[PhotoReason]:
    points = face.points_px()
    centres = [(points[a] + points[b]) / 2 for a, b in _EYE_CENTRES]
    inter_eye = float(np.linalg.norm(centres[0] - centres[1]))
    if inter_eye <= 1.0:
        return []
    pad = _PAD * inter_eye

    def padded(indices: tuple[int, ...]) -> NDArray[np.float32] | None:
        x0, y0 = points[list(indices)].min(axis=0) - pad
        x1, y1 = points[list(indices)].max(axis=0) + pad
        return _box(gray, x0, y0, x1, y1)

    radius = _CHEEK_RADIUS * inter_eye
    cheek_regions = [
        _box(gray, x - radius, y - radius, x + radius, y + radius)
        for x, y in (points[index] for index in _CHEEKS)
    ]
    cheek_pixels = [region for region in cheek_regions if region is not None]
    if not cheek_pixels:
        return []
    cheek = float(np.concatenate(cheek_pixels).mean())
    if cheek < 1.0:
        return []
    eye_regions = [region for region in (padded(eye) for eye in _EYES) if region is not None]
    reasons: list[PhotoReason] = []
    if eye_regions and _covered(np.concatenate(eye_regions), cheek, limits):
        reasons.append(PhotoReason.EYES_COVERED)
    if _covered(padded(_MOUTH), cheek, limits):
        reasons.append(PhotoReason.MOUTH_COVERED)
    return reasons


def check_photo(
    pixels: RgbImage, face: FaceResult, angle: AngleSpec, limits: CheckThresholds
) -> list[PhotoReason]:
    """Run the per-photo checks; an empty list means the photo is accepted.

    Args:
        pixels: The upright RGB photo (as stored).
        face: FaceGeometry's result for ``pixels``.
        angle: The angle this photo was uploaded for.
        limits: The configured thresholds.
    """
    reasons: list[PhotoReason] = []
    height, width = int(pixels.shape[0]), int(pixels.shape[1])
    if width < limits.min_width or height < limits.min_height:
        reasons.append(PhotoReason.TOO_SMALL)
    gray = luminance(pixels)
    if isinstance(face, MultipleFaces):
        reasons.append(PhotoReason.MULTIPLE_FACES)
        return reasons
    if isinstance(face, NoFace):
        if float(gray.mean()) < limits.min_brightness:
            reasons.append(PhotoReason.TOO_DARK)
        reasons.append(PhotoReason.NO_FACE)
        return reasons

    points = face.points_px()
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    region = _box(gray, x0, y0, x1, y1)
    brightness = float(region.mean()) if region is not None else float(gray.mean())
    if brightness < limits.min_brightness:
        reasons.append(PhotoReason.TOO_DARK)
    elif brightness > limits.max_brightness:
        reasons.append(PhotoReason.TOO_BRIGHT)

    box_width = max(0.0, min(float(x1), width) - max(float(x0), 0.0))
    box_height = max(0.0, min(float(y1), height) - max(float(y0), 0.0))
    fraction = (box_width * box_height) / float(width * height)
    if fraction < limits.min_face_fraction:
        reasons.append(PhotoReason.FACE_TOO_SMALL)
    elif fraction > limits.max_face_fraction:
        reasons.append(PhotoReason.FACE_TOO_LARGE)

    if not angle.yaw_min <= face.yaw_degrees <= angle.yaw_max:
        reasons.append(PhotoReason.POSE_MISMATCH)

    reasons.extend(_occlusion(gray, face, limits))
    return reasons
