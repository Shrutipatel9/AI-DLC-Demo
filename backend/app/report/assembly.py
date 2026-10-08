"""Report assembly: the stored analysis result and image slots become the published report.

Pure functions (no I/O). The report is built on request from the stored result, so it is
available the moment the result is stored, with no approval step (AC8.1.2). It never waits on
images (AC8.7.5): an image slot is reported as ``ready``, ``pending`` or ``not_available``.

Rules:
- exactly the 11 features of ``FEATURE_KEYS``, in that order, and no Smile section (AC8.1.1);
- each recommendation sits in exactly one of the three tiers; a missing or invalid stored tier
  is assigned by the keyword rules (AC8.2.1, AC8.2.2);
- a feature without a geometric measurement says so instead of showing empty numbers (AC8.4.2);
- units come from the stored value's name: ``*_degrees`` are degrees, evenness is out of 100,
  every other value is a unitless ratio (AC8.4.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from app.analysis.public import ResultView, SlotView
from app.measurement.public import FEATURE_KEYS
from app.report import template
from app.report.schemas import (
    AssessmentsOut,
    DimorphismOut,
    FaceShapeOut,
    FeatureOut,
    ImageOut,
    MetricOut,
    PrincipleOut,
    RecommendationOut,
    RecommendationsOut,
    RegionScoreOut,
    ReportOut,
    SubSectionOut,
    SymmetryOut,
    TemplateSectionsOut,
    ThirdsOut,
    UnderstandingOut,
)
from app.report_writing.public import AT_HOME, IN_CLINIC, OVER_THE_COUNTER, TIERS, classify

PDF_PATH: Final = "/report/pdf"
_SLOT_STATES: Final[dict[str, str]] = {
    "ready": "ready",
    "pending": "pending",
    "not_available_yet": "not_available",
}
_NO_TEXT: Final = "The text for this feature is not available."


def media_url(file_id: Any) -> str:
    """The owner-checked URL of a stored file."""
    return f"/media/{file_id}"


def metric_label(name: str) -> tuple[str, str]:
    """``(label, unit)`` for a stored value name."""
    base, unit = name, "ratio"
    if name.endswith("_degrees"):
        base, unit = name[: -len("_degrees")], "degrees"
    elif name.endswith("_ratio"):
        base = name[: -len("_ratio")]
    elif name == "skin_tone_evenness":
        unit = "out of 100"
    words = base.replace("_", " ")
    return words[:1].upper() + words[1:], unit


def _metrics(entry: Mapping[str, Any]) -> list[MetricOut]:
    values: Mapping[str, float] = entry.get("values", {}) if entry.get("measured") else {}
    metrics = []
    for name, value in values.items():
        label, unit = metric_label(name)
        metrics.append(MetricOut(name=name, label=label, value=float(value), unit=unit))
    return metrics


def image_out(title: str, slot: SlotView | None) -> ImageOut:
    """A feature's AI image slot with its label and alt text (AC8.7.4)."""
    state = _SLOT_STATES.get(slot.status, "not_available") if slot else "not_available"
    url = None
    if slot is not None and state == "ready":
        if slot.media_file_id is None:
            state = "not_available"
        else:
            url = media_url(slot.media_file_id)
    return ImageOut(
        status=state,
        image_url=url,
        ai_label=template.AI_IMAGE_LABEL,
        alt=f"{template.AI_IMAGE_LABEL} \u2014 {title}",
    )


def _tier_of(item: Any) -> tuple[str, str]:
    """``(text, tier)`` of a stored recommendation; the keyword rules fix a missing tier."""
    if isinstance(item, Mapping):
        text = str(item.get("text", "")).strip()
        tier = item.get("tier")
    else:
        text, tier = str(item).strip(), None
    return text, tier if tier in TIERS else classify(text)


def recommendations_for(report_text: Mapping[str, Any]) -> RecommendationsOut:
    """The report's recommendations in three tiers (AC8.2.1-AC8.2.3)."""
    tiers: dict[str, list[RecommendationOut]] = {AT_HOME: [], OVER_THE_COUNTER: [], IN_CLINIC: []}
    features = report_text.get("features", {})
    for key in FEATURE_KEYS:
        for item in features.get(key, {}).get("recommendations", []):
            text, tier = _tier_of(item)
            if text:
                tiers[tier].append(
                    RecommendationOut(
                        feature=key, feature_title=template.FEATURE_TITLES[key], text=text
                    )
                )
    return RecommendationsOut(
        at_home=tiers[AT_HOME],
        over_the_counter=tiers[OVER_THE_COUNTER],
        in_clinic=tiers[IN_CLINIC],
        tier_captions=dict(template.TIER_CAPTIONS),
        professional_advice_text=template.PROFESSIONAL_ADVICE,
    )


def _assessments(raw: Mapping[str, Any]) -> AssessmentsOut:
    symmetry = raw.get("symmetry")
    thirds = raw.get("facialThirds")
    dimorphism = raw.get("dimorphism")
    shape = raw.get("faceShape")
    prototypicality = raw.get("prototypicality")
    return AssessmentsOut(
        symmetry=None
        if not symmetry
        else SymmetryOut(
            score=int(symmetry["score"]),
            label=str(symmetry["label"]),
            regional_balance=[
                RegionScoreOut(region=str(r["region"]), score=int(r["score"]))
                for r in symmetry.get("regionalBalance", [])
            ],
        ),
        facial_thirds=None
        if not thirds
        else ThirdsOut(
            upper=float(thirds["upper"]),
            middle=float(thirds["middle"]),
            lower=float(thirds["lower"]),
        ),
        dimorphism=None
        if not dimorphism
        else DimorphismOut(
            masculinity=float(dimorphism["masculinity"]),
            femininity=float(dimorphism["femininity"]),
            label=str(dimorphism["label"]),
        ),
        prototypicality=None if prototypicality is None else float(prototypicality),
        face_shape=None
        if not shape
        else FaceShapeOut(
            name=str(shape), description=template.FACE_SHAPE_DESCRIPTIONS.get(str(shape), "")
        ),
    )


def _template_sections() -> TemplateSectionsOut:
    return TemplateSectionsOut(
        introduction=template.INTRODUCTION,
        understanding_your_results=UnderstandingOut(
            intro=template.UNDERSTANDING_INTRO,
            principles=[
                PrincipleOut(title=title, text=text)
                for title, text in template.UNDERSTANDING_PRINCIPLES
            ],
        ),
        limitations=template.LIMITATIONS,
        disclaimer_points=list(template.DISCLAIMER_POINTS),
        privacy_points=list(template.PRIVACY_POINTS),
    )


def assemble(view: ResultView) -> ReportOut:
    """The published report for a stored result (US8.1, US8.2, US8.7)."""
    measurements = view.result.get("measurements", {})
    measured = measurements.get("features", {})
    text = view.result.get("reportText", {})
    written = text.get("features", {})
    slots = {slot.slot_key: slot for slot in view.slots}
    before_url = None if view.front_file_id is None else media_url(view.front_file_id)

    features: list[FeatureOut] = []
    for key in FEATURE_KEYS:
        title = template.FEATURE_TITLES[key]
        entry = measured.get(key, {})
        copy = written.get(key, {})
        features.append(
            FeatureOut(
                key=key,
                title=title,
                narrative=str(copy.get("narrative") or _NO_TEXT),
                summary=str(copy.get("summary") or ""),
                potential_ideas=[str(idea) for idea in copy.get("potentialIdeas", [])],
                metrics=_metrics(entry),
                no_measurement_reason=None
                if entry.get("measured")
                else str(entry.get("noMeasurementReason") or "No measurement is available."),
                before_image_url=before_url,
                before_alt=f"Your photo — {title}",
                after=image_out(title, slots.get(key)),
                sub_sections=[
                    SubSectionOut(heading=heading, body=body)
                    for heading, body in (template.SKIN_SUBSECTIONS if key == "skin" else ())
                ],
            )
        )
    return ReportOut(
        report_id=view.run_id,
        published_at=view.published_at,
        template_version=template.TEMPLATE_VERSION,
        template_sections=_template_sections(),
        assessments=_assessments(measurements.get("assessments", {})),
        features=features,
        recommendations=recommendations_for(text),
        ai_label=template.AI_IMAGE_LABEL,
        pdf_url=PDF_PATH,
    )
