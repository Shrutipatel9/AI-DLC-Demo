"""The report and Home APIs through the real app, worker and pipeline (US8.1, US8.2, US8.4,
US8.7, US11.1, US11.3). The AI text and image vendors are the recording FAKES."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.models import AnalysisImageSlot
from app.measurement.public import FEATURE_KEYS
from app.report import template
from app.report.assembly import metric_label, recommendations_for
from app.report.home import score_label
from tests.factories import SignedInUser
from tests.report.conftest import (
    Harness,
    ImageHarness,
    get_home,
    get_report,
    run_to_done,
)

TITLES = [template.FEATURE_TITLES[key] for key in FEATURE_KEYS]


# --- US8.1: my report, only after payment, only mine -----------------------------------------


def test_the_report_has_exactly_the_11_features_in_order_and_no_smile(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC8.1.1, AC8.1.2: available straight after the run, with no approval step."""
    run_to_done(client, paid, image_harness)

    response = get_report(client, paid)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert [feature["title"] for feature in body["features"]] == TITLES
    assert [feature["key"] for feature in body["features"]] == list(FEATURE_KEYS)
    assert "smile" not in [feature["key"] for feature in body["features"]]
    for feature in body["features"]:
        assert feature["narrative"]
        assert feature["summary"]
        assert feature["potentialIdeas"]
    assert body["pdfUrl"] == "/report/pdf"


def test_without_payment_the_report_is_402_and_another_users_is_never_visible(
    client: TestClient,
    paid: SignedInUser,
    image_harness: ImageHarness,
    make_paid_user: Callable[..., SignedInUser],
    consistent: SignedInUser,
) -> None:
    """AC8.1.3: 402 before payment; user B never sees user A's report."""
    run_to_done(client, paid, image_harness)
    other = make_paid_user()  # paid, photos uploaded, no analysis of their own

    assert get_report(client, other).status_code == 404
    assert get_report(client, other).json()["error"]["code"] == "REPORT_NOT_READY"
    assert get_report(client, paid).status_code == 200
    assert client.get("/report").status_code == 401


def test_an_unpaid_user_gets_402_for_report_home_and_pdf(
    client: TestClient, consistent: SignedInUser
) -> None:
    """AC8.1.3, AC8.5.1: the paywall is enforced on the server for every report route."""
    for path in ("/report", "/home", "/report/pdf"):
        response = client.get(path, headers={"Authorization": f"Bearer {consistent.access_token}"})
        assert response.status_code == 402, path
        assert response.json()["error"]["code"] == "PAYMENT_REQUIRED"


def test_a_paid_user_without_a_run_gets_report_not_ready(
    client: TestClient, paid: SignedInUser
) -> None:
    """Paid but nothing analysed yet: 404 REPORT_NOT_READY, for report and Home."""
    assert get_report(client, paid).json()["error"]["code"] == "REPORT_NOT_READY"
    assert get_home(client, paid).status_code == 404


# --- AC8.1.4 / AC8.7: image slots and text ---------------------------------------------------


def test_each_feature_carries_its_ready_image_with_label_and_alt_text(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC8.1.4, AC8.7.1, AC8.7.4."""
    run_to_done(client, paid, image_harness)

    features = get_report(client, paid).json()["features"]

    for feature in features:
        after = feature["after"]
        assert after["status"] == "ready"
        assert after["imageUrl"].startswith("/media/")
        assert after["aiLabel"] == "AI-generated illustration"
        assert after["alt"] == f"AI-generated illustration — {feature['title']}"
        assert feature["beforeImageUrl"].startswith("/media/")
    nose = next(feature for feature in features if feature["key"] == "nose")
    assert nose["after"]["alt"] == "AI-generated illustration — Nose"


def test_an_image_that_is_not_ready_shows_its_state_and_the_text_still_renders(
    client: TestClient, paid: SignedInUser, harness: Harness, db_session: Session
) -> None:
    """AC8.1.4, AC8.7.5: the U6 placeholder step leaves every slot "not available yet"."""
    run_to_done(client, paid, harness)
    slot = db_session.scalars(
        select(AnalysisImageSlot).where(AnalysisImageSlot.slot_key == "eyes")
    ).one()
    slot.status = "pending"
    db_session.flush()

    features = {f["key"]: f for f in get_report(client, paid).json()["features"]}

    assert features["eyes"]["after"] == {
        "status": "pending",
        "imageUrl": None,
        "aiLabel": "AI-generated illustration",
        "alt": "AI-generated illustration — Eyes",
    }
    assert features["hair"]["after"]["status"] == "not_available"
    assert features["hair"]["narrative"]


def test_template_text_is_exactly_the_configured_text(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC8.7.2, AC8.7.3, AC8.2.3."""
    run_to_done(client, paid, image_harness)

    body = get_report(client, paid).json()

    sections = body["templateSections"]
    assert sections["introduction"] == template.INTRODUCTION
    assert sections["limitations"] == template.LIMITATIONS
    understanding = sections["understandingYourResults"]
    assert understanding["intro"] == template.UNDERSTANDING_INTRO
    assert [(p["title"], p["text"]) for p in understanding["principles"]] == list(
        template.UNDERSTANDING_PRINCIPLES
    )
    assert body["templateVersion"] == template.TEMPLATE_VERSION
    assert body["recommendations"]["professionalAdviceText"] == template.PROFESSIONAL_ADVICE
    assert body["recommendations"]["tierCaptions"] == template.TIER_CAPTIONS


# --- US8.2: three tiers ----------------------------------------------------------------------


def test_every_recommendation_sits_in_exactly_one_tier(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC8.2.1: 3 fake recommendations per feature x 11 features, each in one tier only."""
    run_to_done(client, paid, image_harness)

    recommendations = get_report(client, paid).json()["recommendations"]

    tiers = [recommendations[k] for k in ("atHome", "overTheCounter", "inClinic")]
    assert sum(len(tier) for tier in tiers) == 33
    texts = [(item["feature"], item["text"]) for tier in tiers for item in tier]
    assert len(texts) == len(set(texts))
    assert any("laser" in item["text"] for item in recommendations["inClinic"])
    assert any("moisturiser" in item["text"] for item in recommendations["overTheCounter"])


def test_a_missing_or_invalid_tier_is_assigned_by_the_keyword_rules() -> None:
    """AC8.2.2."""
    text = {
        "features": {
            "skin": {
                "recommendations": [
                    {"text": "Try a niacinamide serum.", "tier": "bogus"},
                    {"text": "Ask about laser options.", "tier": None},
                    "Drink more water.",
                    {"text": "Wear a hat outdoors.", "tier": "in_clinic"},
                ]
            }
        }
    }

    result = recommendations_for(text)

    assert [item.text for item in result.over_the_counter] == ["Try a niacinamide serum."]
    assert [item.text for item in result.in_clinic] == [
        "Ask about laser options.",
        "Wear a hat outdoors.",
    ]
    assert [item.text for item in result.at_home] == ["Drink more water."]


# --- US8.4: metric tables --------------------------------------------------------------------


def test_measured_features_list_units_and_hair_and_neck_say_no_measurement(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC8.4.1, AC8.4.2."""
    run_to_done(client, paid, image_harness)

    features = {f["key"]: f for f in get_report(client, paid).json()["features"]}

    nose = features["nose"]
    assert nose["metrics"]
    assert nose["noMeasurementReason"] is None
    assert all(metric["unit"] in {"ratio", "degrees"} for metric in nose["metrics"])
    for key in ("hair", "neck"):
        assert features[key]["metrics"] == []
        assert features[key]["noMeasurementReason"]
    assert [s["heading"] for s in features["skin"]["subSections"]] == [
        "Skincare Protocol",
        "Further Skin Enhancement",
    ]
    assert features["hair"]["subSections"] == []


def test_metric_labels_and_units_are_plain() -> None:
    assert metric_label("brow_tilt_degrees") == ("Brow tilt", "degrees")
    assert metric_label("nose_width_ratio") == ("Nose width", "ratio")
    assert metric_label("skin_tone_evenness") == ("Skin tone evenness", "out of 100")


# --- US8.3 / US8.8: assessments --------------------------------------------------------------


def test_assessments_carry_the_stored_values(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC8.3.2, AC8.8.1, AC8.8.2."""
    run_to_done(client, paid, image_harness)

    assessments = get_report(client, paid).json()["assessments"]

    assert 0 <= assessments["symmetry"]["score"] <= 100
    assert assessments["symmetry"]["regionalBalance"]
    thirds = assessments["facialThirds"]
    assert abs(thirds["upper"] + thirds["middle"] + thirds["lower"] - 1) < 0.02
    assert assessments["dimorphism"]["label"] in {"more masculine", "more feminine", "balanced"}
    assert assessments["prototypicality"] is not None
    assert assessments["faceShape"]["description"]


# --- US11.1 / US11.3: Home -------------------------------------------------------------------


def test_home_has_stats_priorities_radar_protocol_and_the_pdf_link(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC11.1.2, AC11.1.3, AC11.1.4, AC11.3.1."""
    run_to_done(client, paid, image_harness)

    response = get_home(client, paid)

    assert response.status_code == 200
    body = response.json()
    assert body["reportStatus"] == "ready"
    assert body["pdfUrl"] == "/report/pdf"
    assert 0 <= body["overallScore"] <= 100
    assert body["evaluatedPoints"] > 0
    priorities = body["priorityFeatures"]
    assert len(priorities) == 3
    scores = [p["score"] for p in priorities]
    assert scores == sorted(scores)
    assert all(p["label"] in {"Strong", "Balanced", "Needs attention"} for p in priorities)
    assert [axis["axis"] for axis in body["harmonyProfile"]] == [
        "Harmony",
        "Symmetry",
        "Smoothness",
        "Jawline",
        "Skin",
        "Volume",
    ]
    radar = {axis["axis"]: axis["value"] for axis in body["harmonyProfile"]}
    assert radar["Symmetry"] is not None
    assert radar["Smoothness"] is None  # not measured: never plotted as 0
    protocol = body["protocol"]
    assert protocol["phaseLabel"] == "PHASE 01"
    assert 1 <= len(protocol["actions"]) <= 4
    assert body["beforeImageUrl"].startswith("/media/")
    assert body["potentialImageUrl"].startswith("/media/")


def test_a_feature_with_no_score_is_never_a_priority(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """Hair, Neck and Ears have nothing to compare, so they are not listed (never 0)."""
    run_to_done(client, paid, image_harness)

    priorities = get_home(client, paid).json()["priorityFeatures"]

    assert {p["key"] for p in priorities}.isdisjoint({"hair", "neck", "ears"})


def test_score_labels_use_a_fixed_set() -> None:
    assert score_label(95) == "Strong"
    assert score_label(70) == "Balanced"
    assert score_label(20) == "Needs attention"


def test_unknown_run_ids_are_not_exposed(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    run_to_done(client, paid, image_harness)
    body: dict[str, Any] = get_report(client, paid).json()
    assert uuid.UUID(body["reportId"])
