"""The Skin heuristic (US7.8): how even the skin's brightness is across the face.

[Decided by delivery team] [Assumption] Skin has no geometry, so the one value is
``skin_tone_evenness`` (0-100): the mean brightness of small patches on the forehead, both
cheeks and the chin, and how much those means differ from each other. It is sensitive to
lighting and shadows; it is a first-pass indicator, not a skin-health measurement, and the
narrative is told only to describe it as an observation about the photo.
"""

from __future__ import annotations

import numpy as np

from app.face.public import FaceFound, RgbImage
from app.measurement import landmarks as lm

#: A patch is a square this fraction of the face width on each side.
PATCH_FRACTION = 0.06
#: A coefficient of variation of the patch means at or above this scores 0.
EVENNESS_ZERO_AT = 0.25
MIN_PATCHES = 3

_PATCH_CENTRES = (lm.TOP, lm.CHEEK_R, lm.CHEEK_L, lm.CHIN_TIP)
_LUMINANCE = np.asarray([0.299, 0.587, 0.114], dtype=np.float64)


def skin_tone_evenness(image: RgbImage, found: FaceFound) -> float | None:
    """The evenness score, or ``None`` when too few patches lie inside the photo."""
    points = found.points_px()
    width_px = float(np.linalg.norm(points[lm.FACE_EDGE_R] - points[lm.FACE_EDGE_L]))
    half = max(2, round(PATCH_FRACTION * width_px / 2))
    means: list[float] = []
    for index in _PATCH_CENTRES:
        x, y = round(float(points[index][0])), round(float(points[index][1]))
        if x - half < 0 or y - half < 0 or x + half >= image.shape[1] or y + half >= image.shape[0]:
            continue
        patch = image[y - half : y + half + 1, x - half : x + half + 1].astype(np.float64)
        means.append(float((patch @ _LUMINANCE).mean()))
    if len(means) < MIN_PATCHES:
        return None
    average = float(np.mean(means))
    if average <= 0:
        return None
    variation = float(np.std(means)) / average
    return 100.0 * max(0.0, 1.0 - variation / EVENNESS_ZERO_AT)
