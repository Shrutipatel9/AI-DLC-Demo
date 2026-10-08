"""The privacy-safe AI request (US7.4, FR-008, FR-004).

What the vendor receives: the instructions, the person's photos, the stored measurements and
assessments, and the NON-MEDICAL questionnaire answers with their real question text
(FR-008 a). The caller passes only what the Onboarding port ``get_non_medical_answers``
returned, which by construction never contains a medical-flagged question or its follow-up
(ADR-007); this module adds nothing from any other source.

When the reassurance flag is set (the distress or appearance-frequency answers are at or above
the configured level, AC7.4.3), the instructions ask for an especially measured, reassuring
tone (FR-008 e).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.ai.public import ImageInput, TextMessage
from app.measurement.public import FEATURE_KEYS

REASSURANCE_INSTRUCTION = (
    "The person may be sensitive about their appearance. Write in an especially measured, "
    "gentle and reassuring tone: lead with strengths, never compare them with others, avoid "
    "anything that could sound critical, alarming or like a flaw, and keep every suggestion "
    "optional."
)

_INSTRUCTIONS = """\
You write the feature explanations of a cosmetic facial analysis report. The user message is \
a JSON object with: the 11 feature keys, the measured values per feature, the facial \
assessments, the person's questionnaire answers (question and answer text) and the number of \
decimals to quote. The person's photos follow.

Rules:
- Return one entry for every feature key, exactly once, in the given order.
- Each narrative has 3 to 5 sentences. When a feature has measured values, quote at least one \
of them as a number with exactly the stated number of decimals, in plain words (never use \
field names such as snake_case keys). For a feature with no measurement, describe only what \
the photos show.
- Personalise tone and emphasis to the person's goal, motivation and the features they like \
or dislike, using only the answers provided.
- Give one to three "potential ideas" per feature (gentle, optional possibilities), one short \
summary callout (at most 300 characters) and one to six recommendations.
- Recommendations are informational, never prescriptive, and mention consulting a qualified \
professional where relevant.
- This is cosmetic commentary only: never mention medical conditions, medication, allergies \
or diagnoses, and never answer medical questions.
"""


@dataclass(frozen=True)
class AnswerForAi:
    """A non-medical answer with its question text."""

    question: str
    answer: str


def build_instructions(*, reassure: bool) -> str:
    """The system message, with the reassurance instruction when it applies."""
    return _INSTRUCTIONS + (f"\n{REASSURANCE_INSTRUCTION}\n" if reassure else "")


def build_request(
    *,
    answers: Sequence[AnswerForAi],
    measurements: Mapping[str, Any],
    photos: Sequence[ImageInput],
    reassure: bool,
    decimals: int,
) -> tuple[list[TextMessage], list[ImageInput]]:
    """The messages and photos for the structured report-writing call."""
    context = {
        "featureKeys": list(FEATURE_KEYS),
        "valueDecimals": decimals,
        "measurements": measurements["features"],
        "assessments": measurements["assessments"],
        "questionnaire": [
            {"question": entry.question, "answer": entry.answer} for entry in answers
        ],
    }
    messages = [
        TextMessage("system", build_instructions(reassure=reassure)),
        TextMessage("user", json.dumps(context, sort_keys=True)),
    ]
    return messages, list(photos)
