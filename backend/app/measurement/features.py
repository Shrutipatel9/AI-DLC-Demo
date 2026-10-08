"""Geometric measurements per feature from the front photo's landmark mesh (US7.3, FR-007).

Every value is a unitless ratio or an angle in degrees, so it does not depend on the photo's
size or distance. ``face_width`` (the widest points of the face) and ``face_height`` (top of
the mesh to the chin tip) are the scales.

Ears are measured separately from each side's own 3/4 photo (:func:`ear_values`, US7.7).
The mesh has no ear points, so the ear values are first-pass position heuristics that use the
face-edge landmark on the ear's side; they are labelled that way in the stored result.

[Decided by delivery team] The set of values per feature is a first pass; formulas live here
and are covered by tests. Values are not rounded here (the service rounds them once).
"""

from __future__ import annotations

from app.measurement import landmarks as lm
from app.measurement.geometry import (
    Points,
    angle_degrees,
    dist,
    face_height,
    face_width,
    mid,
    ratio,
    tilt_degrees,
)

Values = dict[str, float]

#: Feature -> the landmark-based measurement function (front photo).
LANDMARK_FEATURES = ("eyebrows", "eyes", "nose", "cheeks", "jaw", "lips", "chin")


def eyebrows(pts: Points) -> Values:
    """Brow length, the gap between brow and eye, and the brow's tilt."""
    width = face_width(pts)
    length = (
        dist(pts, lm.BROW_R_OUTER, lm.BROW_R_INNER) + dist(pts, lm.BROW_L_OUTER, lm.BROW_L_INNER)
    ) / 2.0
    gap = (
        abs(float(pts[lm.EYE_R_TOP][1] - pts[lm.BROW_R_PEAK][1]))
        + abs(float(pts[lm.EYE_L_TOP][1] - pts[lm.BROW_L_PEAK][1]))
    ) / 2.0
    tilt = (
        tilt_degrees(pts[lm.BROW_R_INNER], pts[lm.BROW_R_OUTER])
        + tilt_degrees(pts[lm.BROW_L_INNER], pts[lm.BROW_L_OUTER])
    ) / 2.0
    return {
        "brow_length_ratio": ratio(length, width),
        "brow_eye_gap_ratio": ratio(gap, width),
        "brow_tilt_degrees": tilt,
    }


def eyes(pts: Points) -> Values:
    """Eye width, openness, spacing and the tilt of the line between the corners."""
    width = face_width(pts)
    eye_width = (
        dist(pts, lm.EYE_R_OUTER, lm.EYE_R_INNER) + dist(pts, lm.EYE_L_INNER, lm.EYE_L_OUTER)
    ) / 2.0
    eye_height = (
        dist(pts, lm.EYE_R_TOP, lm.EYE_R_BOTTOM) + dist(pts, lm.EYE_L_TOP, lm.EYE_L_BOTTOM)
    ) / 2.0
    spacing = dist(pts, lm.EYE_R_INNER, lm.EYE_L_INNER)
    tilt = (
        tilt_degrees(pts[lm.EYE_R_INNER], pts[lm.EYE_R_OUTER])
        + tilt_degrees(pts[lm.EYE_L_INNER], pts[lm.EYE_L_OUTER])
    ) / 2.0
    return {
        "eye_width_ratio": ratio(eye_width, width),
        "eye_openness_ratio": ratio(eye_height, eye_width),
        "eye_spacing_ratio": ratio(spacing, eye_width),
        "canthal_tilt_degrees": tilt,
    }


def nose(pts: Points) -> Values:
    """Nose width and length, and the width against the space between the eyes."""
    width = face_width(pts)
    nose_width = dist(pts, lm.ALA_R, lm.ALA_L)
    return {
        "nose_width_ratio": ratio(nose_width, width),
        "nose_length_ratio": ratio(dist(pts, lm.NASION, lm.SUBNASALE), face_height(pts)),
        "nose_to_eye_spacing_ratio": ratio(nose_width, dist(pts, lm.EYE_R_INNER, lm.EYE_L_INNER)),
    }


def cheeks(pts: Points) -> Values:
    """Cheekbone width, how it compares to the jaw, and the fullness of the cheek."""
    cheek_width = face_width(pts)
    return {
        "face_width_to_height_ratio": ratio(cheek_width, face_height(pts)),
        "cheek_to_jaw_ratio": ratio(cheek_width, dist(pts, lm.GONION_R, lm.GONION_L)),
        "cheek_fullness_ratio": ratio(dist(pts, lm.CHEEK_R, lm.CHEEK_L), cheek_width),
    }


def jaw(pts: Points) -> Values:
    """Jaw width, the jaw angle and the length of the jaw line."""
    width = face_width(pts)
    angle = (
        angle_degrees(pts[lm.GONION_R], pts[lm.FACE_EDGE_R], pts[lm.CHIN_TIP])
        + angle_degrees(pts[lm.GONION_L], pts[lm.FACE_EDGE_L], pts[lm.CHIN_TIP])
    ) / 2.0
    length = (dist(pts, lm.GONION_R, lm.CHIN_TIP) + dist(pts, lm.GONION_L, lm.CHIN_TIP)) / 2.0
    return {
        "jaw_width_ratio": ratio(dist(pts, lm.GONION_R, lm.GONION_L), width),
        "jaw_angle_degrees": angle,
        "jaw_length_ratio": ratio(length, width),
    }


def lips(pts: Points) -> Values:
    """Lip width, fullness, the upper-to-lower proportion and the corners' tilt."""
    width = face_width(pts)
    mouth_width = dist(pts, lm.MOUTH_R, lm.MOUTH_L)
    upper = dist(pts, lm.UPPER_LIP_TOP, lm.UPPER_LIP_BOTTOM)
    lower = dist(pts, lm.LOWER_LIP_TOP, lm.LOWER_LIP_BOTTOM)
    centre = mid(pts, lm.UPPER_LIP_BOTTOM, lm.LOWER_LIP_TOP)
    tilt = (tilt_degrees(centre, pts[lm.MOUTH_R]) + tilt_degrees(centre, pts[lm.MOUTH_L])) / 2.0
    return {
        "lip_width_ratio": ratio(mouth_width, width),
        "lip_fullness_ratio": ratio(dist(pts, lm.UPPER_LIP_TOP, lm.LOWER_LIP_BOTTOM), mouth_width),
        "upper_to_lower_lip_ratio": ratio(upper, lower),
        "mouth_corner_tilt_degrees": tilt,
    }


def chin(pts: Points) -> Values:
    """Chin height, chin width and where the lower lip sits above the chin."""
    height = face_height(pts)
    return {
        "chin_height_ratio": ratio(dist(pts, lm.LOWER_LIP_BOTTOM, lm.CHIN_TIP), height),
        "chin_width_ratio": ratio(
            dist(pts, lm.CHIN_R, lm.CHIN_L), dist(pts, lm.GONION_R, lm.GONION_L)
        ),
        "chin_to_nose_ratio": ratio(
            dist(pts, lm.SUBNASALE, lm.CHIN_TIP), dist(pts, lm.NASION, lm.SUBNASALE)
        ),
    }


FEATURE_FUNCTIONS = {
    "eyebrows": eyebrows,
    "eyes": eyes,
    "nose": nose,
    "cheeks": cheeks,
    "jaw": jaw,
    "lips": lips,
    "chin": chin,
}


def ear_values(pts: Points, *, side: str) -> Values:
    """First-pass ear position values from a photo (US7.7).

    The mesh has no ear points, so these use the face-edge landmark on the ear's side:
    where it sits between the brows and the base of the nose (an ear's top should line up
    with the brows and its bottom with the nose base), and how far it is behind the outer
    eye corner. ``side`` is ``"left"`` or ``"right"`` (the person's own).
    """
    anchor, eye_corner = (
        (lm.FACE_EDGE_L, lm.EYE_L_OUTER) if side == "left" else (lm.FACE_EDGE_R, lm.EYE_R_OUTER)
    )
    brow_y = float((pts[lm.BROW_R_PEAK][1] + pts[lm.BROW_L_PEAK][1]) / 2.0)
    nose_base_y = float(pts[lm.SUBNASALE][1])
    return {
        "ear_vertical_position_ratio": ratio(float(pts[anchor][1]) - brow_y, nose_base_y - brow_y),
        "ear_to_eye_distance_ratio": ratio(
            abs(float(pts[anchor][0] - pts[eye_corner][0])), face_height(pts)
        ),
    }
