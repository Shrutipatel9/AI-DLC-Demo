"""ReportWriting: output validation, recommendation tiers, the request and retries (US7.4,
US7.9: AC7.4.3, AC7.9.1, AC7.9.2)."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from app.ai.errors import AiRateLimitError, AiUnavailableError
from app.ai.fakes import FakeTextModel
from app.ai.ports import ImageInput
from app.measurement.public import FEATURE_KEYS
from app.report_writing.public import (
    AT_HOME,
    IN_CLINIC,
    OVER_THE_COUNTER,
    REASSURANCE_INSTRUCTION,
    AnswerForAi,
    ReportWritingFailed,
    ReportWritingService,
    fake_report,
)
from app.report_writing.request import build_request
from app.report_writing.schema import output_schema
from app.report_writing.tiers import classify
from app.report_writing.validation import (
    InvalidReportText,
    cites_a_value,
    count_sentences,
    validate_report_text,
)

PHOTOS = [ImageInput(b"front-bytes", "image/png", "front")]
DECIMALS = 2


def measurements() -> dict[str, Any]:
    features: dict[str, Any] = {}
    for key in FEATURE_KEYS:
        measured = key not in ("hair", "neck")
        features[key] = {
            "measured": measured,
            "values": {f"{key}_value_ratio": 0.31, f"{key}_other_degrees": 12.5}
            if measured
            else {},
            "noMeasurementReason": None if measured else "No mesh.",
        }
    return {"features": features, "assessments": {"symmetry": {"score": 80, "label": "Good"}}}


def valid_output() -> dict[str, Any]:
    return fake_report(*build_request_args())


def build_request_args() -> tuple[list[Any], list[Any], dict[str, Any]]:
    messages, images = build_request(
        answers=[AnswerForAi("What is your goal?", "Refine")],
        measurements=measurements(),
        photos=PHOTOS,
        reassure=False,
        decimals=DECIMALS,
    )
    return messages, images, output_schema()


def service(model: FakeTextModel, sleeps: list[float] | None = None) -> ReportWritingService:
    return ReportWritingService(
        text_model=model,
        max_attempts=3,
        backoff_seconds=1.0,
        decimals=DECIMALS,
        sleep=(sleeps if sleeps is not None else []).append,
    )


def write(svc: ReportWritingService) -> dict[str, Any]:
    return svc.write(
        answers=[AnswerForAi("What is your goal?", "Refine")],
        measurements=measurements(),
        photos=PHOTOS,
        reassure=False,
    )


def test_valid_text_for_all_eleven_features_is_normalised_with_tiered_recommendations() -> None:
    text = validate_report_text(valid_output(), measurements()["features"], DECIMALS)

    assert tuple(text["features"]) == FEATURE_KEYS
    eyes = text["features"]["eyes"]
    assert 3 <= count_sentences(eyes["narrative"]) <= 5
    assert eyes["potentialIdeas"]
    assert eyes["summary"]
    assert {r["tier"] for r in eyes["recommendations"]} == {AT_HOME, OVER_THE_COUNTER, IN_CLINIC}


def test_a_narrative_must_quote_one_of_its_stored_values_at_the_configured_precision() -> None:
    """AC7.9.1."""
    output = valid_output()
    eyes = next(item for item in output["features"] if item["key"] == "eyes")
    eyes["narrative"] = (
        "Your eyes are balanced. They look open and bright. This is a pleasing result."
    )

    with pytest.raises(InvalidReportText) as caught:
        validate_report_text(output, measurements()["features"], DECIMALS)
    assert caught.value.problems == ["eyes: narrative quotes none of the stored values"]

    eyes["narrative"] = (
        "Your eyes measure 0.3 here. They look open. A pleasing result."  # 1 decimal
    )
    with pytest.raises(InvalidReportText):
        validate_report_text(output, measurements()["features"], DECIMALS)

    eyes["narrative"] = "Your eyes measure 0.31 here. They look open. A pleasing result."
    validate_report_text(output, measurements()["features"], DECIMALS)


def test_a_feature_without_a_measurement_needs_no_quoted_value() -> None:
    output = valid_output()
    hair = next(item for item in output["features"] if item["key"] == "hair")
    hair["narrative"] = "Your hair frames your face. It looks healthy. It suits you."
    validate_report_text(output, measurements()["features"], DECIMALS)


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("One. Two. Three.", 3),
        ("A value of 0.31 is shown. Next one! And last?", 3),
        ("Only one sentence", 1),
        ("", 0),
    ],
)
def test_sentences_are_counted_without_splitting_decimals(text: str, count: int) -> None:
    assert count_sentences(text) == count


def test_citation_matches_whole_numbers_only() -> None:
    assert cites_a_value("It is 0.31.", {"a": 0.31}, 2)
    assert not cites_a_value("It is 10.31 units.", {"a": 0.31}, 2)
    assert not cites_a_value("It is 0.312 units.", {"a": 0.31}, 2)


def mutate(change: Any) -> dict[str, Any]:
    output = copy.deepcopy(valid_output())
    change(output)
    return output


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (lambda o: o["features"].pop(), "missing"),
        (lambda o: o["features"].append(copy.deepcopy(o["features"][0])), "appears more than once"),
        (lambda o: o["features"][0].update(key="smile"), "unknown key"),
        (lambda o: o["features"][2].update(narrative="Too short."), "sentences"),
        (lambda o: o["features"][2].update(narrative=" ".join(["Sentence."] * 6)), "sentences"),
        (lambda o: o["features"][2].update(summary="x" * 301), "summary"),
        (lambda o: o["features"][2].update(potentialIdeas=[]), "potential ideas"),
        (lambda o: o["features"][2].update(recommendations=["ok", ""]), "recommendations"),
        (lambda o: o["features"][2].update(recommendations="not a list"), "recommendations"),
        (
            lambda o: o["features"][2].update(
                narrative="Your eyes measure 0.31 here. Ask about your medication. It is fine."
            ),
            "medical wording",
        ),
        (
            lambda o: o["features"][2].update(
                narrative="Your eyes_value_ratio is 0.31 here. It is fine. Really fine."
            ),
            "raw field name",
        ),
    ],
)
def test_invalid_text_is_rejected_and_names_the_rule_never_the_text(
    change: Any, problem: str
) -> None:
    with pytest.raises(InvalidReportText) as caught:
        validate_report_text(mutate(change), measurements()["features"], DECIMALS)
    assert any(problem in line for line in caught.value.problems)


def test_an_answer_without_a_feature_list_is_rejected() -> None:
    with pytest.raises(InvalidReportText):
        validate_report_text({"features": "oops"}, measurements()["features"], DECIMALS)
    with pytest.raises(InvalidReportText):
        validate_report_text({}, measurements()["features"], DECIMALS)


@pytest.mark.parametrize(
    ("text", "tier"),
    [
        ("Apply a vitamin C serum each morning.", OVER_THE_COUNTER),
        ("A gentle cream with SPF helps.", OVER_THE_COUNTER),
        ("Consider seeing a dermatologist.", IN_CLINIC),
        ("Ask about laser options, or a serum.", IN_CLINIC),  # the in-clinic keyword wins
        ("Sleep well and drink water.", AT_HOME),
        ("Massage your jaw gently.", AT_HOME),
    ],
)
def test_recommendations_are_sorted_into_the_three_tiers_by_keyword(text: str, tier: str) -> None:
    """ASM-007."""
    assert classify(text) == tier


def test_the_request_carries_questions_with_answers_measurements_and_the_photos() -> None:
    messages, images = build_request(
        answers=[AnswerForAi("What is your goal?", "Refine"), AnswerForAi("Why?", "A new job")],
        measurements=measurements(),
        photos=PHOTOS,
        reassure=False,
        decimals=DECIMALS,
    )

    context = json.loads(messages[1].content)
    assert context["questionnaire"] == [
        {"question": "What is your goal?", "answer": "Refine"},
        {"question": "Why?", "answer": "A new job"},
    ]
    assert context["featureKeys"] == list(FEATURE_KEYS)
    assert context["valueDecimals"] == DECIMALS
    assert "eyes" in context["measurements"]
    assert images == PHOTOS
    assert REASSURANCE_INSTRUCTION not in messages[0].content


def test_the_reassuring_tone_instruction_is_added_when_asked() -> None:
    """AC7.4.3."""
    messages, _ = build_request(
        answers=[], measurements=measurements(), photos=[], reassure=True, decimals=DECIMALS
    )
    assert REASSURANCE_INSTRUCTION in messages[0].content


def test_valid_output_is_returned_on_the_first_attempt() -> None:
    model = FakeTextModel(fake_report)
    text = write(service(model))
    assert tuple(text["features"]) == FEATURE_KEYS
    assert len(model.calls) == 1
    assert model.calls[0].schema == output_schema()


def test_malformed_output_is_retried_then_accepted() -> None:
    """AC7.9.2."""
    model = FakeTextModel(fake_report)
    model.malformed_next({"features": "oops"}, times=2)
    sleeps: list[float] = []

    text = write(service(model, sleeps))

    assert tuple(text["features"]) == FEATURE_KEYS
    assert len(model.calls) == 3
    assert sleeps == [1.0, 1.0]


def test_output_that_never_validates_fails_with_a_reason_and_returns_nothing() -> None:
    """AC7.9.2: nothing half-valid is published."""
    model = FakeTextModel(fake_report)
    model.malformed_next({"features": []}, times=5)

    with pytest.raises(ReportWritingFailed) as caught:
        write(service(model))
    assert caught.value.reason == "The report text could not be written."
    assert len(model.calls) == 3  # the configured number of attempts


def test_vendor_errors_use_attempts_and_a_rate_limit_waits_as_the_vendor_asks() -> None:
    model = FakeTextModel(fake_report)
    model.fail_next(AiRateLimitError(retry_after=9))
    model.fail_next(AiUnavailableError("down"))
    sleeps: list[float] = []

    write(service(model, sleeps))

    assert sleeps == [9.0, 1.0]
    always_down = FakeTextModel(fake_report)
    always_down.fail_next(AiUnavailableError("down"), times=3)
    with pytest.raises(ReportWritingFailed):
        write(service(always_down))
