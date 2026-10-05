"""Questionnaire definition: the [QS] seed data, branching and the definition rules
(US4.2, US4.4; AC4.2.2-AC4.2.4, AC4.4.1-AC4.4.5; plan decisions D1, D5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.onboarding.definition import (
    DEFAULT_QUESTIONNAIRE_FILE,
    DefinitionError,
    QuestionnaireDefinition,
    answer_text,
    follow_up_visible,
    load_consent_text,
    load_definition,
    visible_questions,
)

QS_DISCLAIMER = (
    "I hereby confirm that I do not have any concerns related to Body Dysmorphic Disorder or "
    "other conditions affecting my perception of my appearance. I understand that treatment "
    "recommendations are purely for informational reasons and not medical guidance. Any "
    "implementation of treatments is at my own discretion."
)


def test_seed_has_the_23_questions_in_order_with_types_and_options(
    seed_definition: QuestionnaireDefinition,
) -> None:
    questions = seed_definition.questions
    assert [q.id for q in questions] == [f"q{n}" for n in range(1, 24)]
    assert [q.order for q in questions] == list(range(1, 24))
    types = {q.id: q.type for q in questions}
    assert [qid for qid, kind in types.items() if kind == "text"] == [
        "q1",
        "q14",
        "q15",
        "q16",
        "q22",
        "q23",
    ]
    assert [qid for qid, kind in types.items() if kind == "multi"] == ["q7"]
    q7 = seed_definition.question("q7")
    assert q7 is not None
    assert len(q7.options) == 13
    assert {o.group for o in q7.options} == {
        "Injectables (minimally invasive)",
        "Non-invasive treatments",
        "Invasive treatments",
        "Semi-permanent enhancements",
    }
    q4 = seed_definition.question("q4")
    assert q4 is not None
    assert [o.label for o in q4.options] == ["Masculine", "Feminine", "No Preference"]


def test_disclaimer_matches_the_specification_exactly(
    seed_definition: QuestionnaireDefinition,
) -> None:
    assert seed_definition.disclaimer_text == QS_DISCLAIMER


def test_medical_flags_are_exactly_q8_to_q12_and_follow_ups_are_q9_and_q11(
    seed_definition: QuestionnaireDefinition,
) -> None:
    assert [q.id for q in seed_definition.questions if q.medical] == [
        "q8",
        "q9",
        "q10",
        "q11",
        "q12",
    ]
    with_follow_up = [q for q in seed_definition.questions if q.follow_up is not None]
    assert [q.id for q in with_follow_up] == ["q9", "q11"]
    assert all(q.medical for q in with_follow_up)


def test_no_placeholder_text_remains_and_open_items_stay_labelled(
    seed_definition: QuestionnaireDefinition,
) -> None:
    visible_text = json.dumps(
        [[q.text, q.placeholder, [o.label for o in q.options]] for q in seed_definition.questions]
    )
    for marker in ("TODO", "TBD", "lorem", "+ free text?", "[Open"):
        assert marker not in visible_text
    notes = {q.id: q.note for q in seed_definition.questions if q.note}
    assert set(notes) == {"q9", "q11", "q19"}
    assert all(note.startswith("[Open — client]") for note in notes.values())


@pytest.mark.parametrize(
    ("q4", "q19_shown"),
    [(None, False), ("feminine", False), ("masculine", True), ("no_preference", True)],
)
def test_q19_branches_on_q4(
    seed_definition: QuestionnaireDefinition, q4: str | None, q19_shown: bool
) -> None:
    values: dict[str, Any] = {} if q4 is None else {"q4": q4}
    ids = [q.id for q in visible_questions(seed_definition, values)]
    assert ("q19" in ids) is q19_shown
    assert len(ids) == (23 if q19_shown else 22)


def test_follow_up_is_revealed_only_by_yes(seed_definition: QuestionnaireDefinition) -> None:
    q9 = seed_definition.question("q9")
    q8 = seed_definition.question("q8")
    assert q9 is not None
    assert q8 is not None
    assert follow_up_visible(q9, True)
    assert not follow_up_visible(q9, False)
    assert not follow_up_visible(q9, None)
    assert not follow_up_visible(q8, True)


def test_answer_text_uses_labels(seed_definition: QuestionnaireDefinition) -> None:
    q7 = seed_definition.question("q7")
    q18 = seed_definition.question("q18")
    q5 = seed_definition.question("q5")
    q9 = seed_definition.question("q9")
    q1 = seed_definition.question("q1")
    assert q7 is not None
    assert q18 is not None
    assert q5 is not None
    assert q9 is not None
    assert q1 is not None
    assert answer_text(q7, ["botox", "laser"], None) == "Botox; Laser"
    assert answer_text(q7, [], None) == "None selected"
    assert answer_text(q18, "refine", None) == "Refine and enhance my facial aesthetic"
    assert answer_text(q5, False, None) == "No"
    assert answer_text(q9, True, "Ibuprofen") == "Yes — Ibuprofen"
    assert answer_text(q1, "Designer", None) == "Designer"


def _base() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(DEFAULT_QUESTIONNAIRE_FILE.read_text(encoding="utf-8"))
    return raw


def _write(tmp_path: Path, raw: object) -> Path:
    path = tmp_path / "definition.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _mutate(change: str) -> dict[str, Any]:
    raw = _base()
    questions = raw["questions"]
    if change == "duplicate-id":
        questions[1]["id"] = "q1"
    elif change == "show-if-forward":
        questions[3]["showIf"] = {"questionId": "q19", "anyOf": [True]}
    elif change == "show-if-bad-value":
        questions[18]["showIf"] = {"questionId": "q4", "anyOf": ["robot"]}
    elif change == "single-without-options":
        questions[1]["options"] = []
    elif change == "options-on-text":
        questions[0]["options"] = [{"value": "a", "label": "A"}]
    elif change == "follow-up-bad-trigger":
        questions[8]["followUp"]["showWhen"] = "maybe"
    elif change == "order-not-increasing":
        questions[2]["order"] = 1
    elif change == "duplicate-option":
        questions[1]["options"][1]["value"] = "never"
    return raw


@pytest.mark.parametrize(
    "change",
    [
        "duplicate-id",
        "show-if-forward",
        "show-if-bad-value",
        "single-without-options",
        "options-on-text",
        "follow-up-bad-trigger",
        "order-not-increasing",
        "duplicate-option",
    ],
)
def test_invalid_definitions_are_refused(tmp_path: Path, change: str) -> None:
    with pytest.raises(DefinitionError, match="Invalid questionnaire definition"):
        load_definition(_write(tmp_path, _mutate(change)))


def test_unreadable_files_are_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(DefinitionError, match="Cannot read"):
        load_definition(broken)
    with pytest.raises(DefinitionError, match="Cannot read"):
        load_consent_text(tmp_path / "missing.json")
    with pytest.raises(DefinitionError, match="Invalid consent text"):
        load_consent_text(_write(tmp_path, {"version": "v"}))
