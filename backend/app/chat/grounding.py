"""What the assistant is told (US10.1, US10.2).

The system instructions always carry the medical-decline instruction (AC10.2.1). The grounding
context is built only from the user's stored report (scores, measurements, feature summaries,
recommendations) and the NON-MEDICAL questionnaire answers the Onboarding port returns; it never
contains a medical, medication or allergy answer (FR-008 f, FR-019, ADR-007).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.ai.public import TextMessage
from app.measurement.public import FEATURE_KEYS
from app.report_writing.public import AnswerForAi

MEDICAL_DECLINE_INSTRUCTION = (
    "You never answer medical or medication questions. If the person asks about a medical "
    "condition, a diagnosis, a symptom, a medication, a supplement dose, an allergy or any "
    "treatment, politely decline to answer it and suggest they speak to a qualified "
    "healthcare professional or dermatologist."
)

INSTRUCTIONS = (
    "You are the Beauty Assistant of a cosmetic facial analysis service. You answer questions "
    "about the person's own report, which is given as JSON in the next message. Use the "
    "report's real values when you explain a result, keep answers short and friendly, and say "
    "so when the report does not contain what they ask about. This is cosmetic commentary "
    "only. Never invent measurements, and never claim the report is a medical assessment.\n"
    + MEDICAL_DECLINE_INSTRUCTION
)


def _recommendation_text(item: Any) -> str:
    if isinstance(item, Mapping):
        return str(item.get("text", "")).strip()
    return str(item).strip()


def build_context(result: Mapping[str, Any], answers: Sequence[AnswerForAi]) -> dict[str, Any]:
    """The grounding object: assessments, per-feature values and text, non-medical answers."""
    measurements = result.get("measurements", {})
    measured = measurements.get("features", {})
    written = result.get("reportText", {}).get("features", {})
    features: dict[str, Any] = {}
    for key in FEATURE_KEYS:
        entry = measured.get(key, {})
        copy = written.get(key, {})
        recommendations = (_recommendation_text(item) for item in copy.get("recommendations", []))
        features[key] = {
            "values": dict(entry.get("values", {})) if entry.get("measured") else {},
            "summary": copy.get("summary", ""),
            "recommendations": [text for text in recommendations if text],
        }
    return {
        "assessments": measurements.get("assessments", {}),
        "features": features,
        "questionnaire": [{"question": a.question, "answer": a.answer} for a in answers],
    }


def build_messages(
    context: Mapping[str, Any], history: Sequence[tuple[str, str]]
) -> list[TextMessage]:
    """System instructions, the grounding, then the conversation so far (oldest first)."""
    messages = [
        TextMessage("system", INSTRUCTIONS),
        TextMessage("system", "The person's report:\n" + json.dumps(context, sort_keys=True)),
    ]
    for role, text in history:
        messages.append(TextMessage("assistant" if role == "assistant" else "user", text))
    return messages
