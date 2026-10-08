"""Per-feature scores for the Home dashboard (US11.1).

[Decided by delivery team] [Assumption] The client names a per-feature score ("Priority
Features to Improve") but not how it is computed. A feature's score is how close its measured
ratios sit to ``assessments.REFERENCE`` (100 is exactly typical), the same first-pass,
placeholder reference the prototypicality heuristic uses. Skin uses its own 0-100 evenness
value. A feature with nothing to compare (Hair, Neck, Ears, or a missing measurement) has NO
score, which is different from a score of 0 and is never plotted as 0.

All functions are pure.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Final

from app.measurement.assessments import REFERENCE

#: Which stored values make up each feature's score.
SCORE_VALUES: Final[dict[str, tuple[str, ...]]] = {
    "eyebrows": ("brow_eye_gap_ratio",),
    "eyes": ("eye_spacing_ratio", "eye_openness_ratio"),
    "nose": ("nose_width_ratio",),
    "cheeks": ("cheek_to_jaw_ratio", "face_width_to_height_ratio"),
    "jaw": ("jaw_width_ratio",),
    "lips": ("lip_width_ratio", "lip_fullness_ratio"),
    "chin": ("chin_height_ratio",),
}

SKIN_VALUE: Final = "skin_tone_evenness"


def z_score(name: str, value: float) -> float:
    """Standard distance of one ratio from its reference mean."""
    mean, spread = REFERENCE[name]
    return (value - mean) / spread


def _score_of(z_values: list[float]) -> int:
    return round(100.0 * math.exp(-0.5 * (sum(z * z for z in z_values) / len(z_values))))


def feature_scores(features: Mapping[str, Any]) -> dict[str, int | None]:
    """``feature key -> 0-100 score`` or ``None`` when the feature cannot be scored."""
    scores: dict[str, int | None] = {}
    for key, entry in features.items():
        values: Mapping[str, float] = entry.get("values", {}) if entry.get("measured") else {}
        if key == "skin" and SKIN_VALUE in values:
            scores[key] = round(max(0.0, min(100.0, float(values[SKIN_VALUE]))))
            continue
        names = [name for name in SCORE_VALUES.get(key, ()) if name in values]
        scores[key] = (
            _score_of([z_score(name, float(values[name])) for name in names]) if names else None
        )
    return scores


def attribute_phrase(name: str, value: float) -> str:
    """A plain phrase for one ratio against its reference ("narrower than typical")."""
    z = z_score(name, value)
    if z <= -1.0:
        return "narrower or smaller than typical"
    if z >= 1.0:
        return "wider or larger than typical"
    return "within the typical range"
