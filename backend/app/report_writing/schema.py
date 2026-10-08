"""The report text the AI must return, as a JSON schema (US7.9, FR-008, FR-009).

One structured answer covers all 11 features. For each: a narrative of 3-5 sentences that
quotes a measured value when there is one, projected-potential ideas, a one-line summary
callout and a flat list of recommendations (sorted into tiers afterwards, ASM-007).
"""

from __future__ import annotations

from typing import Any, Final

from app.measurement.public import FEATURE_KEYS

MIN_SENTENCES: Final = 3
MAX_SENTENCES: Final = 5
MAX_SUMMARY_LENGTH: Final = 300
MAX_IDEAS: Final = 4
MAX_RECOMMENDATIONS: Final = 6


def output_schema() -> dict[str, Any]:
    """The JSON schema of the structured answer."""
    feature: dict[str, Any] = {
        "type": "object",
        "required": ["key", "narrative", "potentialIdeas", "summary", "recommendations"],
        "properties": {
            "key": {"type": "string", "enum": list(FEATURE_KEYS)},
            "narrative": {"type": "string"},
            "potentialIdeas": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_IDEAS,
                "items": {"type": "string"},
            },
            "summary": {"type": "string", "maxLength": MAX_SUMMARY_LENGTH},
            "recommendations": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_RECOMMENDATIONS,
                "items": {"type": "string"},
            },
        },
    }
    return {
        "type": "object",
        "required": ["features"],
        "properties": {
            "features": {
                "type": "array",
                "minItems": len(FEATURE_KEYS),
                "maxItems": len(FEATURE_KEYS),
                "items": feature,
            }
        },
    }
