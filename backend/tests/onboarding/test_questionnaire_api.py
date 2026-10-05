"""Questionnaire API: definition, branching, saving, resuming (US4.2, US4.4; AC4.2.1-AC4.2.7,
AC4.4.1, AC4.4.2; plan decisions D1, D3)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.onboarding.models import QuestionnaireDefinitionRecord, QuestionnaireResponse
from tests.factories import SignedInUser
from tests.onboarding.conftest import bearer, put_answer


def test_definition_lists_23_questions_without_medical_flags_or_notes(
    client: TestClient, consented: SignedInUser
) -> None:
    response = client.get("/onboarding/questionnaire", headers=bearer(consented.access_token))
    assert response.status_code == 200
    body = response.json()
    assert body["definitionVersion"] == "qs-v1"
    assert body["disclaimerText"].startswith("I hereby confirm")
    assert "supportUrl" not in body  # none configured, none invented
    assert len(body["questions"]) == 23
    for question in body["questions"]:
        assert "medical" not in question
        assert "note" not in question
    q19 = body["questions"][18]
    assert q19["showIf"] == {"questionId": "q4", "anyOf": ["masculine", "no_preference"]}
    q9 = body["questions"][8]
    assert q9["followUp"] == {
        "showWhen": True,
        "type": "text",
        "label": "Please list your medications",
        "maxLength": 2000,
    }
    assert body["questions"][6]["options"][0] == {
        "value": "botox",
        "label": "Botox",
        "group": "Injectables (minimally invasive)",
    }
    assert response.headers["Cache-Control"] == "no-store"


def test_progress_starts_empty_with_22_visible(client: TestClient, consented: SignedInUser) -> None:
    body = client.get("/onboarding/response", headers=bearer(consented.access_token)).json()
    assert body == {
        "answers": {},
        "visibleQuestionIds": [f"q{n}" for n in range(1, 24) if n != 19],
        "submitted": False,
        "submittedAt": None,
    }


def test_branching_answer_shows_then_hides_q19(client: TestClient, consented: SignedInUser) -> None:
    shown = put_answer(client, consented, "q4", "masculine").json()
    assert "q19" in shown["visibleQuestionIds"]
    assert len(shown["visibleQuestionIds"]) == 23
    assert put_answer(client, consented, "q19", True).status_code == 200
    hidden = put_answer(client, consented, "q4", "feminine").json()
    assert "q19" not in hidden["visibleQuestionIds"]
    assert len(hidden["visibleQuestionIds"]) == 22
    # The earlier Q19 answer is kept while editing, so switching back restores it (AC4.2.5).
    again = put_answer(client, consented, "q4", "no_preference").json()
    assert again["answers"]["q19"] == {"value": True, "followUpText": None}


def test_saving_a_hidden_or_unknown_question_is_refused(
    client: TestClient, consented: SignedInUser
) -> None:
    hidden = put_answer(client, consented, "q19", True)
    assert hidden.status_code == 422
    assert hidden.json()["error"]["details"] == [
        {"field": "questionId", "reason": "QUESTION_HIDDEN"}
    ]
    unknown = put_answer(client, consented, "q99", "x")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"
    bad_id = put_answer(client, consented, "Q1;drop", "x")
    assert bad_id.status_code == 422


def test_answers_are_validated_by_type(client: TestClient, consented: SignedInUser) -> None:
    not_option = put_answer(client, consented, "q2", "weekly")
    assert not_option.status_code == 422
    assert not_option.json()["error"] == {
        "code": "VALIDATION_FAILED",
        "message": "Some of the information you entered isn't valid.",
        "details": [{"field": "value", "reason": "NOT_AN_OPTION"}],
        "requestId": not_option.json()["error"]["requestId"],
    }
    wrong_shape = put_answer(client, consented, "q5", 1)  # numbers are never coerced
    assert wrong_shape.status_code == 422
    assert wrong_shape.json()["error"]["code"] == "VALIDATION_FAILED"
    too_long = put_answer(client, consented, "q23", "x" * 2001)
    assert too_long.status_code == 422


def test_answers_are_kept_and_resumed_with_question_text_and_medical_flag(
    client: TestClient, consented: SignedInUser, db_session: Session
) -> None:
    put_answer(client, consented, "q1", "Designer")
    put_answer(client, consented, "q9", True, "Ibuprofen")
    put_answer(client, consented, "q9", True, "Ibuprofen, vitamin D")  # editable (AC4.2.5)
    put_answer(client, consented, "q7", ["botox", "laser"])
    # A fresh read, as after signing in again (AC4.2.6).
    body = client.get("/onboarding/response", headers=bearer(consented.access_token)).json()
    assert body["answers"] == {
        "q1": {"value": "Designer", "followUpText": None},
        "q9": {"value": True, "followUpText": "Ibuprofen, vitamin D"},
        "q7": {"value": ["botox", "laser"], "followUpText": None},
    }
    stored = db_session.scalars(
        select(QuestionnaireResponse).where(
            QuestionnaireResponse.user_id == uuid.UUID(consented.user_id)
        )
    ).one()
    assert stored.definition_version == "qs-v1"
    assert stored.answers["q9"]["questionText"].startswith("Are you taking any medications")
    assert stored.answers["q9"]["medical"] is True
    assert stored.answers["q1"]["medical"] is False
    assert db_session.get(QuestionnaireDefinitionRecord, "qs-v1") is not None


def test_follow_up_is_dropped_when_the_answer_no_longer_reveals_it(
    client: TestClient, consented: SignedInUser
) -> None:
    put_answer(client, consented, "q11", True, "Latex")
    body = put_answer(client, consented, "q11", False, "Latex").json()
    assert body["answers"]["q11"] == {"value": False, "followUpText": None}
