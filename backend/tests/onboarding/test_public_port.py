"""The public read port: medical answers never leave Onboarding (ADR-007; AC4.4.3; plan
decision D4), plus the onboarding-state helpers for later units (C6)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.onboarding.definition import QuestionnaireDefinition
from app.onboarding.models import QuestionnaireResponse
from app.onboarding.public import (
    get_non_medical_answers,
    get_onboarding_state,
    require_submitted_questionnaire,
)
from app.onboarding.services import OnboardingService
from app.platform.errors import QuestionnaireNotSubmitted
from tests.factories import SignedInUser
from tests.onboarding.conftest import answer_all, submit

CANARY = "CANARY-MEDICAL-7f3a"


def _submitted(
    client: TestClient, user: SignedInUser, definition: QuestionnaireDefinition
) -> uuid.UUID:
    answer_all(
        client,
        user,
        definition,
        overrides={
            "q9": (True, f"{CANARY} meds"),
            "q11": (True, f"{CANARY} allergies"),
            "q14": ("My eye color", None),
        },
    )
    assert submit(client, user).status_code == 200
    return uuid.UUID(user.user_id)


def test_non_medical_answers_exclude_q8_to_q12_and_their_follow_ups(
    client: TestClient,
    consented: SignedInUser,
    seed_definition: QuestionnaireDefinition,
    onboarding: OnboardingService,
    db_session: Session,
) -> None:
    user_id = _submitted(client, consented, seed_definition)
    answers = get_non_medical_answers(onboarding, db_session, user_id)
    ids = [a.question_id for a in answers]
    assert ids == [f"q{n}" for n in range(1, 24) if n not in (8, 9, 10, 11, 12)]
    assert all(CANARY not in a.answer_text for a in answers)
    assert all(CANARY not in a.question_text for a in answers)


def test_non_medical_answers_carry_question_text_and_readable_answers(
    client: TestClient,
    consented: SignedInUser,
    seed_definition: QuestionnaireDefinition,
    onboarding: OnboardingService,
    db_session: Session,
) -> None:
    user_id = _submitted(client, consented, seed_definition)
    by_id = {a.question_id: a for a in get_non_medical_answers(onboarding, db_session, user_id)}
    assert by_id["q14"].question_text == "What feature do you like the most about your face?"
    assert by_id["q14"].answer_text == "My eye color"
    assert by_id["q2"].answer_text == "Never"
    assert by_id["q4"].answer_text == "Masculine"
    assert by_id["q5"].answer_text == "Yes"
    assert by_id["q7"].answer_text == "Botox"


def test_a_stored_medical_mark_is_also_excluded(
    client: TestClient,
    consented: SignedInUser,
    seed_definition: QuestionnaireDefinition,
    onboarding: OnboardingService,
    db_session: Session,
) -> None:
    user_id = _submitted(client, consented, seed_definition)
    row = db_session.scalars(
        select(QuestionnaireResponse).where(QuestionnaireResponse.user_id == user_id)
    ).one()
    answers = dict(row.answers)
    answers["q14"] = {**answers["q14"], "medical": True}
    row.answers = answers
    db_session.commit()
    ids = [a.question_id for a in get_non_medical_answers(onboarding, db_session, user_id)]
    assert "q14" not in ids


def test_nothing_is_returned_before_submission_and_state_tracks_progress(
    client: TestClient,
    consented: SignedInUser,
    seed_definition: QuestionnaireDefinition,
    onboarding: OnboardingService,
    db_session: Session,
) -> None:
    user_id = uuid.UUID(consented.user_id)
    answer_all(client, consented, seed_definition)
    assert get_non_medical_answers(onboarding, db_session, user_id) == []
    state = get_onboarding_state(onboarding, db_session, user_id)
    assert (state.consented, state.submitted) == (True, False)
    with pytest.raises(QuestionnaireNotSubmitted):
        require_submitted_questionnaire(onboarding, db_session, user_id)
    assert submit(client, consented).status_code == 200
    assert get_onboarding_state(onboarding, db_session, user_id).submitted is True
    require_submitted_questionnaire(onboarding, db_session, user_id)
