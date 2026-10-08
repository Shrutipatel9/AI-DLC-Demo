"""Validation of the AI's report text (AC7.9.1, AC7.9.2).

Nothing half-valid is ever kept: :func:`validate_report_text` either returns the normalised
text for all 11 features or raises :class:`InvalidReportText`. Problem messages name the
feature and the rule, never the text itself.

Checks per feature: the key is one of the 11 and appears once; the narrative has 3-5
sentences; a measured feature's narrative quotes at least one of its stored values at the
configured precision; potential ideas, summary and recommendations are present and sized; no
raw measurement field name appears; no medical, medication or allergy wording appears
(FR-008 f).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.measurement.public import FEATURE_KEYS
from app.report_writing import schema, tiers

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
#: [Decided by delivery team] Wording that must never reach cosmetic commentary (FR-008 f).
FORBIDDEN_WORDS = ("medication", "allerg", "diagnos")


class InvalidReportText(Exception):  # noqa: N818  (reads better at the raise site)
    """The AI's text failed validation. ``problems`` are safe to log."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


def count_sentences(text: str) -> int:
    """How many sentences ``text`` has (a decimal point inside a number is not a break)."""
    return len([part for part in _SENTENCE_BREAK.split(text.strip()) if part.strip()])


def format_value(value: float, decimals: int) -> str:
    """A stored value as a narrative must quote it."""
    return f"{value:.{decimals}f}"


def cites_a_value(narrative: str, values: Mapping[str, float], decimals: int) -> bool:
    """Whether ``narrative`` quotes at least one of ``values`` at the configured precision."""
    for value in values.values():
        pattern = rf"(?<![\d.]){re.escape(format_value(value, decimals))}(?!\d)"
        if re.search(pattern, narrative):
            return True
    return False


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_list(value: Any, maximum: int) -> list[str] | None:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        return None
    items = [_text(item) for item in value]
    return None if any(item is None for item in items) else [item for item in items if item]


def validate_report_text(
    output: Mapping[str, Any],
    feature_measurements: Mapping[str, Mapping[str, Any]],
    decimals: int,
) -> dict[str, Any]:
    """The normalised text, ``{"features": {key: {...}}}``, with every recommendation tiered.

    Args:
        output: The AI's structured answer.
        feature_measurements: The stored ``features`` measurements (``values`` per feature).
        decimals: ``REPORT_VALUE_DECIMALS``.

    Raises:
        InvalidReportText: When any rule fails.
    """
    raw_features = output.get("features")
    if not isinstance(raw_features, list):
        raise InvalidReportText(["the answer has no feature list"])
    raw_names = {name for item in feature_measurements.values() for name in item.get("values", {})}
    problems: list[str] = []
    result: dict[str, Any] = {}
    for item in raw_features:
        key = item.get("key") if isinstance(item, dict) else None
        if key not in FEATURE_KEYS:
            problems.append("a feature has an unknown key")
            continue
        if key in result:
            problems.append(f"{key}: appears more than once")
            continue
        entry, found = _validate_feature(key, item, feature_measurements.get(key, {}), decimals)
        problems.extend(f"{key}: {problem}" for problem in found)
        problems.extend(f"{key}: {p}" for p in _wording_problems(item, raw_names))
        result[key] = entry
    problems.extend(f"{key}: missing" for key in FEATURE_KEYS if key not in result)
    if problems:
        raise InvalidReportText(problems)
    return {"features": {key: result[key] for key in FEATURE_KEYS}}


def _validate_feature(
    key: str, item: Mapping[str, Any], measurement: Mapping[str, Any], decimals: int
) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    narrative = _text(item.get("narrative"))
    if narrative is None:
        problems.append("no narrative")
    else:
        sentences = count_sentences(narrative)
        if not schema.MIN_SENTENCES <= sentences <= schema.MAX_SENTENCES:
            problems.append(f"narrative has {sentences} sentences")
        values = measurement.get("values", {}) if measurement.get("measured") else {}
        if values and not cites_a_value(narrative, values, decimals):
            problems.append("narrative quotes none of the stored values")
    ideas = _string_list(item.get("potentialIdeas"), schema.MAX_IDEAS)
    if ideas is None:
        problems.append("potential ideas are missing or malformed")
    summary = _text(item.get("summary"))
    if summary is None or len(summary) > schema.MAX_SUMMARY_LENGTH:
        problems.append("summary is missing or too long")
    recommendations = _string_list(item.get("recommendations"), schema.MAX_RECOMMENDATIONS)
    if recommendations is None:
        problems.append("recommendations are missing or malformed")
    entry = {
        "narrative": narrative,
        "potentialIdeas": ideas,
        "summary": summary,
        "recommendations": [
            {"text": text, "tier": tiers.classify(text)} for text in recommendations or []
        ],
    }
    return entry, problems


def _wording_problems(item: Mapping[str, Any], raw_names: set[str]) -> list[str]:
    parts: list[str] = []
    for field in ("narrative", "summary"):
        value = item.get(field)
        if isinstance(value, str):
            parts.append(value)
    for field in ("potentialIdeas", "recommendations"):
        value = item.get(field)
        if isinstance(value, list):
            parts.extend(entry for entry in value if isinstance(entry, str))
    text = " ".join(parts).lower()
    problems: list[str] = []
    if any(word in text for word in FORBIDDEN_WORDS):
        problems.append("medical wording is not allowed")
    if any(name in text for name in raw_names):
        problems.append("a raw field name appears in the text")
    return problems
