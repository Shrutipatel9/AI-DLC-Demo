"""Answer validation per question type (plan decision D3; US4.2, AC4.2.4)."""

from __future__ import annotations

import pytest

from app.onboarding.definition import (
    Question,
    QuestionnaireDefinition,
    is_answered,
    validate_answer,
)
from app.platform.errors import ValidationFailed


def _q(definition: QuestionnaireDefinition, question_id: str) -> Question:
    question = definition.question(question_id)
    assert question is not None
    return question


@pytest.mark.parametrize(
    ("question_id", "value", "reason"),
    [
        ("q5", "yes", "WRONG_TYPE"),  # Yes/No needs a boolean
        ("q2", True, "WRONG_TYPE"),
        ("q2", "weekly", "NOT_AN_OPTION"),
        ("q7", ["botox", "botox"], "DUPLICATE_OPTION"),
        ("q7", ["botox", "surgery"], "NOT_AN_OPTION"),
        ("q7", "botox", "WRONG_TYPE"),
        ("q1", "   ", "REQUIRED"),
        ("q1", "x" * 501, "TOO_LONG"),
        ("q1", ["a"], "WRONG_TYPE"),
    ],
)
def test_invalid_values_are_refused_with_a_reason(
    seed_definition: QuestionnaireDefinition, question_id: str, value: object, reason: str
) -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_answer(_q(seed_definition, question_id), value, None)
    assert caught.value.details == [{"field": "value", "reason": reason}]


def test_valid_values_are_normalised(seed_definition: QuestionnaireDefinition) -> None:
    assert validate_answer(_q(seed_definition, "q1"), "  Designer ", None) == ("Designer", None)
    assert validate_answer(_q(seed_definition, "q2"), "never", None) == ("never", None)
    assert validate_answer(_q(seed_definition, "q7"), [], None) == ([], None)  # optional
    assert validate_answer(_q(seed_definition, "q23"), "", None) == ("", None)  # optional
    assert validate_answer(_q(seed_definition, "q5"), False, None) == (False, None)


def test_follow_up_is_kept_only_while_revealed(seed_definition: QuestionnaireDefinition) -> None:
    q9 = _q(seed_definition, "q9")
    assert validate_answer(q9, True, "  Ibuprofen ") == (True, "Ibuprofen")
    assert validate_answer(q9, True, "   ") == (True, None)
    assert validate_answer(q9, False, "Ibuprofen") == (False, None)
    assert validate_answer(_q(seed_definition, "q8"), True, "ignored") == (True, None)


def test_follow_up_longer_than_its_limit_is_refused(
    seed_definition: QuestionnaireDefinition,
) -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_answer(_q(seed_definition, "q11"), True, "x" * 2001)
    assert caught.value.details == [{"field": "followUpText", "reason": "TOO_LONG"}]


def test_is_answered_respects_required(seed_definition: QuestionnaireDefinition) -> None:
    assert not is_answered(_q(seed_definition, "q1"), None)
    assert not is_answered(_q(seed_definition, "q1"), "")
    assert is_answered(_q(seed_definition, "q23"), "")
    assert is_answered(_q(seed_definition, "q7"), [])
    assert is_answered(_q(seed_definition, "q5"), False)
