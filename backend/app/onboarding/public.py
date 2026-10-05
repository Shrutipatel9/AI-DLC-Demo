"""The onboarding module's public interface (contract C6). Other modules import only this.

- ``build_onboarding``: wires the service from settings (used by the app factory); it
  loads and validates the consent text and the questionnaire seed file, so bad content
  fails start-up instead of a request.
- ``router``: the ``/onboarding/*`` routes (mounted as protected routes).
- ``get_non_medical_answers``: submitted answers with question text, NEVER including a
  medical-flagged answer or its follow-up (ADR-007; plan decision D4). There is no public
  query that returns medical answers.
- ``get_onboarding_state``: consent and submission flags (for the Journey).
- ``require_submitted_questionnaire``: guard for later steps (409
  ``QUESTIONNAIRE_NOT_SUBMITTED``).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.onboarding.definition import (
    DEFAULT_CONSENT_FILE,
    DEFAULT_QUESTIONNAIRE_FILE,
    load_consent_text,
    load_definition,
)
from app.onboarding.routes import router
from app.onboarding.services import AnsweredQuestion, OnboardingService, OnboardingState
from app.platform.clock import Clock
from app.platform.errors import QuestionnaireNotSubmitted
from app.platform.settings import Settings

__all__ = [
    "AnsweredQuestion",
    "OnboardingService",
    "OnboardingState",
    "build_onboarding",
    "get_non_medical_answers",
    "get_onboarding_state",
    "require_submitted_questionnaire",
    "router",
]


def build_onboarding(settings: Settings, *, clock: Clock) -> OnboardingService:
    """Create the onboarding service from settings and the seed files (D1, D2).

    Raises:
        app.onboarding.definition.DefinitionError: When a seed file is missing or invalid.
    """
    return OnboardingService(
        clock=clock,
        consent=load_consent_text(settings.onboarding_consent_file or DEFAULT_CONSENT_FILE),
        definition=load_definition(
            settings.onboarding_questionnaire_file or DEFAULT_QUESTIONNAIRE_FILE
        ),
        support_url=settings.onboarding_support_url,
    )


def get_non_medical_answers(
    service: OnboardingService, session: Session, user_id: uuid.UUID
) -> list[AnsweredQuestion]:
    """Non-medical, submitted answers with question text (C6 ``answers_for_ai``; ADR-007)."""
    return service.non_medical_answers(session, user_id)


def get_onboarding_state(
    service: OnboardingService, session: Session, user_id: uuid.UUID
) -> OnboardingState:
    """Whether the user consented and submitted (C6 ``onboarding_state``)."""
    return service.state(session, user_id)


def require_submitted_questionnaire(
    service: OnboardingService, session: Session, user_id: uuid.UUID
) -> None:
    """Refuse a later step until the questionnaire is submitted.

    Raises:
        QuestionnaireNotSubmitted: 409 when the questionnaire is not submitted.
    """
    if not service.state(session, user_id).submitted:
        raise QuestionnaireNotSubmitted()
