"""Small geometry helpers on landmark points in pixel space.

Every function is pure and deterministic: the same landmarks always give the same numbers
(AC7.3.2, AC7.5.3, AC7.10.2). Points are first levelled so a tilted head does not distort
widths and heights.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from app.face.public import FaceFound
from app.measurement import landmarks as lm

Points = NDArray[np.float64]


def level(found: FaceFound) -> Points:
    """The landmarks in pixels, rotated so the line between the outer eye corners is level."""
    pts = found.points_px()
    a = pts[lm.EYE_R_OUTER]
    b = pts[lm.EYE_L_OUTER]
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    centre = (a + b) / 2.0
    cos, sin = math.cos(-angle), math.sin(-angle)
    rotation = np.asarray([[cos, -sin], [sin, cos]], dtype=np.float64)
    return np.asarray((pts - centre) @ rotation.T, dtype=np.float64)


def dist(pts: Points, i: int, j: int) -> float:
    """Distance between landmarks ``i`` and ``j``."""
    return float(np.linalg.norm(pts[i] - pts[j]))


def mid(pts: Points, i: int, j: int) -> Points:
    """The point halfway between landmarks ``i`` and ``j``."""
    return np.asarray((pts[i] + pts[j]) / 2.0, dtype=np.float64)


def angle_degrees(vertex: Points, a: Points, b: Points) -> float:
    """The angle at ``vertex`` between the rays to ``a`` and ``b``, in degrees."""
    u = a - vertex
    v = b - vertex
    denominator = float(np.linalg.norm(u) * np.linalg.norm(v))
    if denominator == 0.0:
        return 0.0
    cosine = float(np.clip(np.dot(u, v) / denominator, -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def tilt_degrees(from_point: Points, to_point: Points) -> float:
    """Slope of the line from ``from_point`` to ``to_point``: positive when ``to`` is higher.

    Image y grows downwards, so "higher" means a smaller y.
    """
    dx = float(abs(to_point[0] - from_point[0]))
    dy = float(from_point[1] - to_point[1])
    return math.degrees(math.atan2(dy, dx)) if dx > 0 else 0.0


def face_width(pts: Points) -> float:
    """Distance between the widest points of the face (the scale of every ratio)."""
    return dist(pts, lm.FACE_EDGE_R, lm.FACE_EDGE_L)


def face_height(pts: Points) -> float:
    """Distance from the top of the mesh to the chin tip."""
    return dist(pts, lm.TOP, lm.CHIN_TIP)


def ratio(numerator: float, denominator: float) -> float:
    """``numerator / denominator``, or 0 when the denominator is 0."""
    return numerator / denominator if denominator else 0.0
