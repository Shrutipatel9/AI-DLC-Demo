"""The text fake's default answer: a valid report built from the request's own context.

Used only when ``AI_TEXT_PROVIDER=fake`` (development and test). It reads the JSON context the
request builder wrote, quotes the first stored value of each measured feature at the requested
precision, and returns text that passes validation, so the whole pipeline can be exercised
without a vendor.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.ai.public import ImageInput, TextMessage
from app.measurement.public import FEATURE_KEYS

_RECOMMENDATIONS = (
    "Keep a regular sleep routine and drink enough water through the day.",
    "A daily moisturiser with sunscreen is an easy, low-effort habit.",
    "If you are curious about in-clinic options such as laser, ask a qualified professional.",
)


def fake_report(
    messages: Sequence[TextMessage],
    _images: Sequence[ImageInput],
    _schema: dict[str, Any],
) -> dict[str, Any]:
    """A valid structured answer for the context in the last user message."""
    context = json.loads(next(m.content for m in reversed(messages) if m.role == "user"))
    decimals = int(context["valueDecimals"])
    entries: list[dict[str, Any]] = []
    for key in FEATURE_KEYS:
        measured = context["measurements"].get(key, {})
        values: dict[str, float] = measured.get("values", {}) if measured.get("measured") else {}
        if values:
            value = next(iter(values.values()))
            cited = f"A measured value for this feature is {value:.{decimals}f}."
        else:
            cited = "This feature is described from your photos alone."
        narrative = (
            f"Your {key} are looked at with care in this sample report. "
            f"{cited} "
            "This is a sample sentence written by a test double. "
            "It never replaces the advice of a qualified professional."
        )
        entries.append(
            {
                "key": key,
                "narrative": narrative,
                "potentialIdeas": [f"A gentle, optional idea for your {key}."],
                "summary": f"Sample summary for your {key}.",
                "recommendations": list(_RECOMMENDATIONS),
            }
        )
    return {"features": entries}
