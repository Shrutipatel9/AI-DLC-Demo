"""FaceMeasurement: measurements and assessments of one person's photos (US7.3-US7.10).

Mesh-based features are measured from the front photo; each ear from its own side's 3/4
photo, falling back to the front photo when that side's photo is missing (or shows no single
face); Hair, Skin and Neck use a documented heuristic or an explicit "no measurement" marker
and never an invented number (AC7.8.1).

The result is a plain JSON-ready dict (it is stored as-is). All numbers are rounded once, here,
to ``REPORT_VALUE_DECIMALS``, so a narrative that quotes a stored value quotes exactly what is
stored (AC7.9.1). Nothing here calls the network, and nothing is cached: the same photos give
the same result (AC7.3.2, AC7.5.3, AC7.10.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.face.public import FaceFound, FaceGeometry, RgbImage
from app.measurement import assessments, features
from app.measurement.geometry import Points, level
from app.measurement.skin import skin_tone_evenness

#: The 11 report features, in the report's order (FR-009, BR-008).
FEATURE_KEYS: tuple[str, ...] = (
    "hair",
    "eyebrows",
    "eyes",
    "nose",
    "cheeks",
    "jaw",
    "lips",
    "chin",
    "skin",
    "neck",
    "ears",
)

FRONT = "front"
#: Each ear is measured from its own side's 3/4 photo (angle id).
EAR_ANGLES: dict[str, str] = {"left": "left_3q", "right": "right_3q"}

NO_MEASUREMENT_REASONS: dict[str, str] = {
    "hair": "The face mesh does not cover hair, so hair is described from the photo only.",
    "neck": "The photos are framed on the face, so the neck is described from the photo only.",
}


class MeasurementError(Exception):
    """The photos cannot be measured (no single face in the front photo)."""


class MeasurementService:
    """Measures a photo set.

    Args:
        geometry: The landmark service (the same one photo checks use, AC1.11).
        decimals: Rounding of every stored number (``REPORT_VALUE_DECIMALS``).
        bands: Symmetry label bands, highest first (``SYMMETRY_LABEL_BANDS``).
    """

    def __init__(
        self,
        *,
        geometry: FaceGeometry,
        decimals: int,
        bands: tuple[tuple[str, float], ...],
    ) -> None:
        self.geometry = geometry
        self.decimals = decimals
        self.bands = bands

    def measure(self, front: RgbImage, sides: Mapping[str, RgbImage | None]) -> dict[str, Any]:
        """Measure and assess.

        Args:
            front: The front photo.
            sides: Angle id -> photo for the 3/4 photos; a missing angle (or ``None``) makes
                that ear fall back to the front photo (AC7.7.2).

        Raises:
            MeasurementError: When the front photo has no single face.
        """
        found = self.geometry.detect(front)
        if not isinstance(found, FaceFound):
            raise MeasurementError("The front photo does not show exactly one face.")
        pts = level(found)

        feature_results: dict[str, Any] = {}
        for key in FEATURE_KEYS:
            if key in features.FEATURE_FUNCTIONS:
                feature_results[key] = _measured(features.FEATURE_FUNCTIONS[key](pts), FRONT)
            elif key == "ears":
                feature_results[key] = self._ears(pts, sides)
            elif key == "skin":
                feature_results[key] = self._skin(front, found)
            else:
                feature_results[key] = _no_measurement(key)

        ratios = assessments.shape_ratios(pts)
        result: dict[str, Any] = {
            "features": feature_results,
            "assessments": {
                "symmetry": assessments.symmetry(pts, self.bands),
                "facialThirds": assessments.facial_thirds(pts),
                "dimorphism": assessments.dimorphism(ratios),
                "prototypicality": assessments.prototypicality(ratios),
                "faceShape": assessments.face_shape(ratios),
            },
        }
        rounded: dict[str, Any] = _round(result, self.decimals)
        return rounded

    # ----------------------------------------------------------------------------------------
    def _ears(self, front_pts: Points, sides: Mapping[str, RgbImage | None]) -> dict[str, Any]:
        values: dict[str, float] = {}
        sources: dict[str, str] = {}
        for side, angle in EAR_ANGLES.items():
            pts, source = front_pts, FRONT
            image = sides.get(angle)
            if image is not None:
                side_found = self.geometry.detect(image)
                if isinstance(side_found, FaceFound):
                    pts, source = level(side_found), angle
            for name, value in features.ear_values(pts, side=side).items():
                values[f"{side}_{name}"] = value
            sources[side] = source
        return {
            "measured": True,
            "method": "landmark position heuristic",
            "source": sources,
            "values": values,
            "noMeasurementReason": None,
        }

    def _skin(self, front: RgbImage, found: FaceFound) -> dict[str, Any]:
        evenness = skin_tone_evenness(front, found)
        if evenness is None:
            return _no_measurement(
                "skin", "Too little of the face is inside the photo to compare the skin."
            )
        return {
            "measured": True,
            "method": "brightness heuristic",
            "source": FRONT,
            "values": {"skin_tone_evenness": evenness},
            "noMeasurementReason": None,
        }


def _measured(values: Mapping[str, float], source: str) -> dict[str, Any]:
    return {
        "measured": True,
        "method": "landmark geometry",
        "source": source,
        "values": dict(values),
        "noMeasurementReason": None,
    }


def _no_measurement(key: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "measured": False,
        "method": "none",
        "source": None,
        "values": {},
        "noMeasurementReason": reason or NO_MEASUREMENT_REASONS[key],
    }


def _round(value: Any, decimals: int) -> Any:
    """Round every float in a nested structure; leave ints, strings and bools alone."""
    if isinstance(value, float):
        return round(value, decimals)
    if isinstance(value, dict):
        return {key: _round(item, decimals) for key, item in value.items()}
    if isinstance(value, list):
        return [_round(item, decimals) for item in value]
    return value
