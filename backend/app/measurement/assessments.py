"""Facial Assessments from the front landmarks (US7.5, US7.10, FR9.5).

[Decided by delivery team] [Assumption] Everything here is a documented first-pass heuristic,
as the client accepted ("subject to calibration", US7.10). The numbers that need calibration
are named constants with their meaning:

- symmetry: each mirror pair of landmarks is reflected across the face's vertical midline;
  the distance between the reflection and the real partner, as a fraction of the face width,
  is the error. An error of ``SYMMETRY_ZERO_AT`` (10 % of the width) or more scores 0 for that
  pair; no error scores 100. A region is the mean of its pairs; the overall score is the mean
  of the regions, rounded to a whole number (the stored score is what the label bands use).
- facial thirds: top of the mesh (the mesh stops below the hairline) to the glabella, to the
  base of the nose, to the chin tip, as shares of the total height.
- dimorphism, prototypicality and face shape use ``REFERENCE`` (mean and spread of each ratio).
  The reference values below come from MediaPipe's canonical face mesh and are NOT population
  statistics; they are placeholders until real reference data is chosen.

All functions are pure: the same landmarks always give the same result.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from app.measurement import features
from app.measurement import landmarks as lm
from app.measurement.geometry import Points, dist, face_height, face_width, ratio

SYMMETRY_ZERO_AT = 0.10

#: ``name -> (mean, spread)`` of the ratios used for prototypicality and dimorphism.
REFERENCE: dict[str, tuple[float, float]] = {
    "face_width_to_height_ratio": (0.93, 0.07),
    "jaw_width_ratio": (0.82, 0.05),
    "cheek_to_jaw_ratio": (1.22, 0.10),
    "eye_spacing_ratio": (1.24, 0.12),
    "eye_openness_ratio": (0.22, 0.04),
    "nose_width_ratio": (0.28, 0.025),
    "lip_width_ratio": (0.32, 0.03),
    "chin_height_ratio": (0.20, 0.03),
    "brow_eye_gap_ratio": (0.13, 0.02),
    "lip_fullness_ratio": (0.30, 0.05),
}

#: Ratios that point to a more masculine (+1) or feminine (-1) structure, first pass.
DIMORPHISM_DIRECTION: dict[str, int] = {
    "jaw_width_ratio": 1,
    "face_width_to_height_ratio": 1,
    "chin_height_ratio": 1,
    "brow_eye_gap_ratio": -1,
    "lip_fullness_ratio": -1,
}
DIMORPHISM_STEP = 15.0
DIMORPHISM_BALANCED_BAND = 10.0


def label_for_score(score: float, bands: tuple[tuple[str, float], ...]) -> str:
    """The label of the highest band whose minimum is at or below ``score`` (AC7.5.2).

    ``bands`` is ordered highest first and always ends with a band starting at 0.
    """
    for label, minimum in bands:
        if score >= minimum:
            return label
    return bands[-1][0]


def symmetry(pts: Points, bands: tuple[tuple[str, float], ...]) -> dict[str, Any]:
    """The 0-100 score, its label and the Regional Balance breakdown (US7.5)."""
    width = face_width(pts)
    midline_x = float(np.mean([pts[i][0] for i in lm.MIDLINE]))
    regions: dict[str, float] = {}
    for region, pairs in lm.SYMMETRY_REGIONS.items():
        errors = []
        for right, left in pairs:
            mirrored = np.asarray([2.0 * midline_x - pts[right][0], pts[right][1]])
            errors.append(float(np.linalg.norm(mirrored - pts[left])) / width)
        score = 100.0 * max(0.0, 1.0 - (sum(errors) / len(errors)) / SYMMETRY_ZERO_AT)
        regions[region] = score
    overall = round(sum(regions.values()) / len(regions))
    return {
        "score": overall,
        "label": label_for_score(overall, bands),
        "regionalBalance": [
            {"region": region, "score": round(score)} for region, score in regions.items()
        ],
    }


def facial_thirds(pts: Points) -> dict[str, float]:
    """Upper, middle and lower thirds as shares of the face height (they sum to 1)."""
    top = float(pts[lm.TOP][1])
    glabella = float(pts[lm.GLABELLA][1])
    base = float(pts[lm.SUBNASALE][1])
    chin = float(pts[lm.CHIN_TIP][1])
    total = chin - top
    return {
        "upper": ratio(glabella - top, total),
        "middle": ratio(base - glabella, total),
        "lower": ratio(chin - base, total),
    }


def shape_ratios(pts: Points) -> dict[str, float]:
    """The ratios the dimorphism, prototypicality and face-shape heuristics read."""
    values: dict[str, float] = {}
    for function in (
        features.eyebrows,
        features.eyes,
        features.nose,
        features.cheeks,
        features.jaw,
        features.lips,
        features.chin,
    ):
        values.update(function(pts))
    values["forehead_to_cheek_ratio"] = ratio(dist(pts, lm.TEMPLE_R, lm.TEMPLE_L), face_width(pts))
    values["face_length_to_width_ratio"] = ratio(face_height(pts), face_width(pts))
    return values


def _z(name: str, value: float) -> float:
    mean, spread = REFERENCE[name]
    return (value - mean) / spread


def dimorphism(ratios: Mapping[str, float]) -> dict[str, Any]:
    """Masculine/feminine balance as two indexes that sum to 100, and a label (US7.10)."""
    signed = [DIMORPHISM_DIRECTION[name] * _z(name, ratios[name]) for name in DIMORPHISM_DIRECTION]
    masculine = float(np.clip(50.0 + DIMORPHISM_STEP * (sum(signed) / len(signed)), 0.0, 100.0))
    if masculine >= 50.0 + DIMORPHISM_BALANCED_BAND:
        label = "more masculine"
    elif masculine <= 50.0 - DIMORPHISM_BALANCED_BAND:
        label = "more feminine"
    else:
        label = "balanced"
    return {"masculinity": masculine, "femininity": 100.0 - masculine, "label": label}


def prototypicality(ratios: Mapping[str, float]) -> float:
    """How typical the proportions are against ``REFERENCE``: 100 is exactly typical."""
    squares = [_z(name, ratios[name]) ** 2 for name in REFERENCE]
    return 100.0 * math.exp(-0.5 * (sum(squares) / len(squares)))


def face_shape(ratios: Mapping[str, float]) -> str:
    """A first-pass face shape from length-to-width, jaw, cheek and forehead widths."""
    length_to_width = ratios["face_length_to_width_ratio"]
    jaw_to_cheek = 1.0 / ratios["cheek_to_jaw_ratio"] if ratios["cheek_to_jaw_ratio"] else 1.0
    forehead_to_cheek = ratios["forehead_to_cheek_ratio"]
    if length_to_width >= 1.20:
        return "oblong"
    if length_to_width <= 0.95:
        return "square" if jaw_to_cheek >= 0.92 else "round"
    if jaw_to_cheek < 0.78 and forehead_to_cheek >= 0.9:
        return "heart"
    if jaw_to_cheek < 0.82 and forehead_to_cheek < 0.82:
        return "diamond"
    if jaw_to_cheek >= 0.92:
        return "square"
    return "oval"
