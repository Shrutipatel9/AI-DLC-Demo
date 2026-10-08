"""Home Overview data from the stored result (US11.1, US11.3).

[Decided by delivery team] where the specification leaves a rule open ([RD] 13.1, 14, 4):
- Priority Features to Improve: the three scorable features with the lowest score (ties keep
  the report's order). A feature with no score is never listed and never counted as 0.
- Labels come from a fixed set: 80 and above "Strong", 60 and above "Balanced", otherwise
  "Needs attention".
- Overall score: the mean of the scorable feature scores. Evaluated points: how many stored
  measurement values the report rests on. Analysis time: run start to completion.
- Radar (six axes): Harmony = overall score, Symmetry = the symmetry score, Smoothness = not
  measured (no texture measurement exists, so it is ``None``, not 0), Jawline = the Jaw score,
  Skin = the Skin score, Volume = the Lips score (lip fullness).
- Protocol: Phase 01 only (later phases are open in [RD] 14); its action lines are the user's
  own at-home recommendations, taken from the priority features first, so each traces to a
  finding already shown. Items marked TBD in the specification are left out.
- The "potential" image is the first ready AI "after" image in report order.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from app.analysis.public import ResultView
from app.measurement.public import (
    FEATURE_KEYS,
    SCORE_VALUES,
    attribute_phrase,
    feature_scores,
)
from app.report import template
from app.report.assembly import PDF_PATH, image_out, media_url, metric_label, recommendations_for
from app.report.schemas import (
    HomeOut,
    PriorityAttributeOut,
    PriorityFeatureOut,
    ProtocolOut,
    RadarAxisOut,
)

PRIORITY_COUNT: Final = 3
MAX_ATTRIBUTES: Final = 3
MAX_ACTIONS: Final = 4
STRONG_AT: Final = 80
BALANCED_AT: Final = 60
EVEN_SKIN_AT: Final = 70
RADAR_AXES: Final = ("Harmony", "Symmetry", "Smoothness", "Jawline", "Skin", "Volume")


def score_label(score: int) -> str:
    """The fixed qualitative label of a score band."""
    if score >= STRONG_AT:
        return "Strong"
    if score >= BALANCED_AT:
        return "Balanced"
    return "Needs attention"


def _attributes(key: str, entry: Mapping[str, Any], score: int) -> list[PriorityAttributeOut]:
    values: Mapping[str, float] = entry.get("values", {})
    if key == "skin":
        value = "Fairly even" if score >= EVEN_SKIN_AT else "Noticeably uneven"
        return [PriorityAttributeOut(name="Tone evenness", value=value)]
    return [
        PriorityAttributeOut(
            name=metric_label(name)[0], value=attribute_phrase(name, float(values[name]))
        )
        for name in SCORE_VALUES.get(key, ())
        if name in values
    ][:MAX_ATTRIBUTES]


def assemble_home(view: ResultView) -> HomeOut:
    """The dashboard for a stored result."""
    measurements = view.result.get("measurements", {})
    measured: Mapping[str, Any] = measurements.get("features", {})
    scores = feature_scores(measured)
    scored = [(key, scores[key]) for key in FEATURE_KEYS if scores.get(key) is not None]
    overall = (
        round(sum(score for _, score in scored if score is not None) / len(scored))
        if scored
        else None
    )

    lowest = sorted(scored, key=lambda item: item[1] if item[1] is not None else 0)[:PRIORITY_COUNT]
    priorities = [
        PriorityFeatureOut(
            key=key,
            title=template.FEATURE_TITLES[key],
            score=score,
            label=score_label(score),
            attributes=_attributes(key, measured.get(key, {}), score),
        )
        for key, score in lowest
        if score is not None
    ]

    symmetry = measurements.get("assessments", {}).get("symmetry")
    radar_values: dict[str, int | None] = {
        "Harmony": overall,
        "Symmetry": None if not symmetry else int(symmetry["score"]),
        "Smoothness": None,
        "Jawline": scores.get("jaw"),
        "Skin": scores.get("skin"),
        "Volume": scores.get("lips"),
    }

    recommendations = recommendations_for(view.result.get("reportText", {}))
    priority_keys = [priority.key for priority in priorities]
    at_home = sorted(
        recommendations.at_home,
        key=lambda item: priority_keys.index(item.feature) if item.feature in priority_keys else 99,
    )
    actions = [f"{item.feature_title}: {item.text}" for item in at_home[:MAX_ACTIONS]]

    slots = {slot.slot_key: slot for slot in view.slots}
    potential_url = None
    for key in FEATURE_KEYS:
        image = image_out(template.FEATURE_TITLES[key], slots.get(key))
        if image.status == "ready":
            potential_url = image.image_url
            break

    finished = view.completed_at or view.published_at
    points = sum(
        len(entry.get("values", {})) for entry in measured.values() if entry.get("measured")
    )
    return HomeOut(
        report_status="ready",
        overall_score=overall,
        evaluated_points=points,
        analysis_duration_seconds=max(0, round((finished - view.started_at).total_seconds())),
        priority_features=priorities,
        harmony_profile=[RadarAxisOut(axis=axis, value=radar_values[axis]) for axis in RADAR_AXES],
        protocol=ProtocolOut(
            phase_label=template.PROTOCOL_PHASE_LABEL,
            title=template.PROTOCOL_PHASE_TITLE,
            timing=template.PROTOCOL_TIMING,
            actions=actions,
            closing=template.PROTOCOL_CLOSING,
        ),
        before_image_url=None if view.front_file_id is None else media_url(view.front_file_id),
        potential_image_url=potential_url,
        ai_label=template.AI_IMAGE_LABEL,
        published_at=view.published_at,
        pdf_url=PDF_PATH,
    )
