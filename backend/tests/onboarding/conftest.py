"""Onboarding test fixtures: the real app (from the identity fixtures), users created through
the real API, the real seed definition ([QS]) and helpers to answer it."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.onboarding.definition import QuestionnaireDefinition, load_definition
from app.onboarding.services import OnboardingService
from app.platform.email.fake import RecordingEmailSender
from tests.factories import SignedInUser, verified_user
from tests.identity.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    app,
    bearer,
    client,
    email_fake,
    settings_overrides,
)

#: A valid answer per question type, used to fill the questionnaire.
TEXT_ANSWER = "Designer"


@pytest.fixture(scope="session")
def seed_definition() -> QuestionnaireDefinition:
    """The real questionnaire seed file (unit-test instructions: load the real seed)."""
    return load_definition()


@pytest.fixture
def onboarding(app: FastAPI) -> OnboardingService:  # noqa: F811
    """The service wired on the app under test."""
    service: OnboardingService = app.state.onboarding
    return service


@pytest.fixture
def user(client: TestClient, email_fake: RecordingEmailSender) -> SignedInUser:  # noqa: F811
    """A verified, signed-in user without consent."""
    return verified_user(client, email_fake)


def give_consent(api: TestClient, user: SignedInUser) -> dict[str, Any]:
    """Consent to the current text version through the API."""
    state = api.get("/onboarding/consent", headers=bearer(user.access_token)).json()
    response = api.post(
        "/onboarding/consent",
        json={"consentTextVersion": state["consentTextVersion"]},
        headers=bearer(user.access_token),
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def consented(client: TestClient, user: SignedInUser) -> SignedInUser:  # noqa: F811
    """A signed-in user who has consented to the current text."""
    give_consent(client, user)
    return user


def put_answer(
    api: TestClient,
    user: SignedInUser,
    question_id: str,
    value: object,
    follow_up_text: str | None = None,
) -> Any:
    """PUT one answer and return the response."""
    body: dict[str, Any] = {"value": value}
    if follow_up_text is not None:
        body["followUpText"] = follow_up_text
    return api.put(
        f"/onboarding/response/answers/{question_id}",
        json=body,
        headers=bearer(user.access_token),
    )


def sample_value(definition: QuestionnaireDefinition, question_id: str) -> object:
    """A valid answer for the question (first option, Yes, or a short text)."""
    question = definition.question(question_id)
    assert question is not None
    if question.type == "yesno":
        return True
    if question.type == "single":
        return question.options[0].value
    if question.type == "multi":
        return [question.options[0].value]
    return TEXT_ANSWER


def answer_all(
    api: TestClient,
    user: SignedInUser,
    definition: QuestionnaireDefinition,
    *,
    q4: str = "masculine",
    overrides: dict[str, tuple[object, str | None]] | None = None,
) -> Any:
    """Answer every visible question in order; returns the last progress body."""
    extra = overrides or {}
    body: Any = None
    for question in definition.questions:
        if question.id == "q19" and q4 == "feminine":
            continue
        value, follow_up = extra.get(question.id, (sample_value(definition, question.id), None))
        if question.id == "q4":
            value = q4
        response = put_answer(api, user, question.id, value, follow_up)
        assert response.status_code == 200, (question.id, response.text)
        body = response.json()
    return body


def submit(api: TestClient, user: SignedInUser, confirmed: object = True) -> Any:
    """POST the submit request."""
    return api.post(
        "/onboarding/response/submit",
        json={"disclaimerConfirmed": confirmed},
        headers=bearer(user.access_token),
    )
