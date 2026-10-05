"""Submit with the disclaimer and required checks (US4.3; AC4.2.7, AC4.3.2, AC4.3.3; BR-003;
plan decision D3)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.onboarding.definition import QuestionnaireDefinition
from app.onboarding.models import QuestionnaireResponse
from app.platform.clock import FrozenClock
from tests.factories import SignedInUser
from tests.onboarding.conftest import answer_all, bearer, put_answer, submit


def test_unanswered_required_questions_are_listed(
    client: TestClient, consented: SignedInUser
) -> None:
    put_answer(client, consented, "q1", "Designer")
    response = submit(client, consented)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    missing = [item["field"] for item in error["details"]]
    assert "q1" not in missing
    assert missing[0] == "q2"
    assert "q7" not in missing  # optional
    assert "q23" not in missing  # optional
    assert "q19" not in missing  # hidden until Q4 is answered
    assert all(item["reason"] == "REQUIRED" for item in error["details"])


def test_submit_without_the_disclaimer_is_refused(
    client: TestClient, consented: SignedInUser, seed_definition: QuestionnaireDefinition
) -> None:
    answer_all(client, consented, seed_definition)
    for body in ({"disclaimerConfirmed": False}, {}):
        response = client.post(
            "/onboarding/response/submit", json=body, headers=bearer(consented.access_token)
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "DISCLAIMER_REQUIRED"
    progress = client.get("/onboarding/response", headers=bearer(consented.access_token))
    assert progress.json()["submitted"] is False
    assert len(progress.json()["answers"]) == 23  # answers are kept (AC4.3.4)


def test_submit_marks_the_questionnaire_submitted(
    client: TestClient,
    consented: SignedInUser,
    seed_definition: QuestionnaireDefinition,
    frozen_clock: FrozenClock,
    db_session: Session,
) -> None:
    answer_all(client, consented, seed_definition)
    frozen_clock.advance(minutes=3)
    response = submit(client, consented)
    assert response.status_code == 200
    body = response.json()
    assert body["submitted"] is True
    assert body["submittedAt"].startswith("2026-10-01T10:03:00")
    row = db_session.scalars(
        select(QuestionnaireResponse).where(
            QuestionnaireResponse.user_id == uuid.UUID(consented.user_id)
        )
    ).one()
    assert row.status == "submitted"
    assert row.disclaimer_accepted_at == row.submitted_at
    assert set(row.answers) == {f"q{n}" for n in range(1, 24)}
    for question_id, entry in row.answers.items():
        question = seed_definition.question(question_id)
        assert question is not None
        assert entry["questionText"] == question.text
        assert entry["medical"] is question.medical


def test_answers_cannot_change_after_submission(
    client: TestClient, consented: SignedInUser, seed_definition: QuestionnaireDefinition
) -> None:
    answer_all(client, consented, seed_definition)
    assert submit(client, consented).status_code == 200
    again = submit(client, consented)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "QUESTIONNAIRE_ALREADY_SUBMITTED"
    change = put_answer(client, consented, "q1", "Pilot")
    assert change.status_code == 409
    assert change.json()["error"]["code"] == "QUESTIONNAIRE_ALREADY_SUBMITTED"


def test_hidden_answers_are_dropped_on_submit(
    client: TestClient, consented: SignedInUser, seed_definition: QuestionnaireDefinition
) -> None:
    answer_all(client, consented, seed_definition, q4="masculine")
    put_answer(client, consented, "q4", "feminine")
    body = submit(client, consented).json()
    assert body["submitted"] is True
    assert "q19" not in body["answers"]
    assert len(body["answers"]) == 22


def test_submit_with_nothing_saved_reports_every_required_question(
    client: TestClient, consented: SignedInUser
) -> None:
    response = submit(client, consented)
    assert response.status_code == 422
    assert len(response.json()["error"]["details"]) == 20  # 22 visible minus q7 and q23
