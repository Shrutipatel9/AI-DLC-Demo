"""Report wire models (camelCase JSON). Additive to contract C1 [Decided by delivery team].

The contract names the report and dashboard shapes loosely; these models are the concrete wire
form. Recommendation items carry their feature, the dashboard route is ``GET /home`` (the U8
plan), and an image slot carries its own AI label and alt text.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PrincipleOut(CamelModel):
    """One of the four "Understanding Your Results" points."""

    title: str
    text: str


class UnderstandingOut(CamelModel):
    """The preamble shown before any score or feature (AC8.7.2)."""

    intro: str
    principles: list[PrincipleOut]


class TemplateSectionsOut(CamelModel):
    """The configured template text (AC8.7.3)."""

    introduction: str
    understanding_your_results: UnderstandingOut
    limitations: str
    disclaimer_points: list[str]
    privacy_points: list[str]


class RegionScoreOut(CamelModel):
    """One Regional Balance entry."""

    region: str
    score: int


class SymmetryOut(CamelModel):
    """Symmetry score out of 100, its label and the Regional Balance breakdown (AC8.3.2)."""

    score: int
    label: str
    regional_balance: list[RegionScoreOut]


class ThirdsOut(CamelModel):
    """The three facial proportions as shares of the face height (they sum to 1)."""

    upper: float
    middle: float
    lower: float


class DimorphismOut(CamelModel):
    """Masculine/feminine balance (display only, AC8.8.1)."""

    masculinity: float
    femininity: float
    label: str


class FaceShapeOut(CamelModel):
    """The face shape and a plain description (AC8.8.2)."""

    name: str
    description: str


class AssessmentsOut(CamelModel):
    """The facial assessments."""

    symmetry: SymmetryOut | None
    facial_thirds: ThirdsOut | None
    dimorphism: DimorphismOut | None
    prototypicality: float | None
    face_shape: FaceShapeOut | None


class MetricOut(CamelModel):
    """One stored measurement with its unit (AC8.4.1)."""

    name: str
    label: str
    value: float
    unit: str


class ImageOut(CamelModel):
    """A feature's AI "after" image slot (AC8.1.4, AC8.7.4, AC8.7.5)."""

    status: Literal["ready", "pending", "not_available"]
    image_url: str | None
    ai_label: str
    alt: str


class SubSectionOut(CamelModel):
    """A named sub-section of a feature (Skin: Skincare Protocol, [RT] 10)."""

    heading: str
    body: str


class FeatureOut(CamelModel):
    """One of the 11 feature sections."""

    key: str
    title: str
    narrative: str
    summary: str
    potential_ideas: list[str]
    metrics: list[MetricOut]
    no_measurement_reason: str | None
    before_image_url: str | None
    before_alt: str
    after: ImageOut
    sub_sections: list[SubSectionOut]


class RecommendationOut(CamelModel):
    """One recommendation, in exactly one tier (AC8.2.1)."""

    feature: str
    feature_title: str
    text: str


class RecommendationsOut(CamelModel):
    """The three tiers, their captions and the static advice (AC8.2.3)."""

    at_home: list[RecommendationOut]
    over_the_counter: list[RecommendationOut]
    in_clinic: list[RecommendationOut]
    tier_captions: dict[str, str]
    professional_advice_text: str


class ReportOut(CamelModel):
    """The published report (``GET /report``)."""

    report_id: uuid.UUID
    published_at: datetime
    template_version: str
    template_sections: TemplateSectionsOut
    assessments: AssessmentsOut
    features: list[FeatureOut]
    recommendations: RecommendationsOut
    ai_label: str
    pdf_url: str


class PriorityAttributeOut(CamelModel):
    """One plain attribute line under a priority feature."""

    name: str
    value: str


class PriorityFeatureOut(CamelModel):
    """A feature to improve first (the three lowest scores)."""

    key: str
    title: str
    score: int
    label: str
    attributes: list[PriorityAttributeOut]


class RadarAxisOut(CamelModel):
    """One of the six radar axes; ``value`` is ``None`` when not measured (never 0)."""

    axis: str
    value: int | None


class ProtocolOut(CamelModel):
    """The Treatment Protocol card (Phase 01, [RT] 3.7)."""

    phase_label: str
    title: str
    timing: str
    actions: list[str]
    closing: str


class HomeOut(CamelModel):
    """Home Overview data (``GET /home``)."""

    report_status: Literal["ready"]
    overall_score: int | None
    evaluated_points: int
    analysis_duration_seconds: int | None
    priority_features: list[PriorityFeatureOut]
    harmony_profile: list[RadarAxisOut]
    protocol: ProtocolOut
    before_image_url: str | None
    potential_image_url: str | None
    ai_label: str
    published_at: datetime
    pdf_url: str
