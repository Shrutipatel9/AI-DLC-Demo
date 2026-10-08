"""The FaceMeasurement module's public interface. Other modules import only this.

- ``build_measurement``: the service from settings and the shared landmark service.
- ``FEATURE_KEYS``: the 11 report features in order (FR-009).
- ``feature_scores`` / ``attribute_phrase``: per-feature scores for Home (U8).
- ``MeasurementError``: the front photo cannot be measured.
"""

from __future__ import annotations

from app.face.public import FaceGeometry
from app.measurement.assessments import label_for_score
from app.measurement.scoring import SCORE_VALUES, attribute_phrase, feature_scores
from app.measurement.service import (
    EAR_ANGLES,
    FEATURE_KEYS,
    FRONT,
    MeasurementError,
    MeasurementService,
)
from app.platform.settings import Settings

__all__ = [
    "EAR_ANGLES",
    "FEATURE_KEYS",
    "FRONT",
    "SCORE_VALUES",
    "MeasurementError",
    "MeasurementService",
    "attribute_phrase",
    "build_measurement",
    "feature_scores",
    "label_for_score",
]


def build_measurement(settings: Settings, *, geometry: FaceGeometry) -> MeasurementService:
    """Create the measurement service from settings."""
    return MeasurementService(
        geometry=geometry,
        decimals=settings.report_value_decimals,
        bands=settings.symmetry_bands,
    )
