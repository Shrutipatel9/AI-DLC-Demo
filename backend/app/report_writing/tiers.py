"""Recommendation tiers by keyword rules (ASM-007, FR-012, OQ-012).

[Assumption] ASM-007 is NOT yet confirmed by the client: the AI returns a flat list of
recommendations per feature and these rules sort each into one of the three tiers. It is a
first-pass judgment call, not a clinical classification; expect some misclassification and a
later tuning pass.

- ``in_clinic``: anything that mentions a professional, a clinic or a procedure
  ("consider seeing a dermatologist", "laser", ...), checked first so it wins over the others;
- ``over_the_counter``: products ("serum", "cream", ...);
- ``at_home``: everything else.
"""

from __future__ import annotations

import re
from typing import Final

AT_HOME: Final = "at_home"
OVER_THE_COUNTER: Final = "over_the_counter"
IN_CLINIC: Final = "in_clinic"
TIERS: Final = (AT_HOME, OVER_THE_COUNTER, IN_CLINIC)

IN_CLINIC_KEYWORDS: Final = (
    "dermatologist",
    "consider seeing",
    "aesthetic practitioner",
    "clinic",
    "laser",
    "filler",
    "botox",
    "injectable",
    "injection",
    "microneedling",
    "chemical peel",
    "radiofrequency",
    "ipl",
)
OVER_THE_COUNTER_KEYWORDS: Final = (
    "serum",
    "cream",
    "moisturizer",
    "moisturiser",
    "sunscreen",
    "spf",
    "retinol",
    "niacinamide",
    "vitamin c",
    "hyaluronic",
    "peptide",
    "cleanser",
    "exfoliant",
    "lotion",
    "over-the-counter",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(keyword)}", text) for keyword in keywords)


def classify(recommendation: str) -> str:
    """The tier of one recommendation: ``in_clinic``, ``over_the_counter`` or ``at_home``."""
    text = recommendation.lower()
    if _contains_any(text, IN_CLINIC_KEYWORDS):
        return IN_CLINIC
    if _contains_any(text, OVER_THE_COUNTER_KEYWORDS):
        return OVER_THE_COUNTER
    return AT_HOME
