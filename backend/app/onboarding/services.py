"""Onboarding service: consent gate, questionnaire progress, answer saving and submission.

Plan decisions:
- D2: every questionnaire action requires consent to the CURRENT consent text version,
  otherwise 403 ``CONSENT_REQUIRED``.
- D3: answers are saved one per request; submit checks every required visible question is
  answered (422 ``VALIDATION_FAILED``), then the disclaimer (422 ``DISCLAIMER_REQUIRED``).
- D4: :meth:`OnboardingService.non_medical_answers` is the only way answers leave this
  module, and it never returns a medical-flagged answer or its follow-up (ADR-007).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.onboarding import repositories
from app.onboarding.definition import (
    AnswerValue,
    ConsentText,
    QuestionnaireDefinition,
    answer_text,
    follow_up_visible,
    is_answered,
    validate_answer,
    visible_questions,
)
from app.onboarding.models import QuestionnaireResponse, ResponseStatus
from app.platform.clock import Clock
from app.platform.errors import (
    ConsentRequired,
    ConsentVersionChanged,
    DisclaimerRequired,
    NotFound,
    QuestionnaireAlreadySubmitted,
    ValidationFailed,
)

logger = logging.getLogger("onboarding")


@dataclass(frozen=True)
class ConsentView:
    """The current consent text and whether this user agreed to it."""

    version: str
    text: str
    agreement: str
    given: bool
    given_at: datetime | None


@dataclass(frozen=True)
class SavedAnswer:
    """One of the user's own answers, as shown back to them."""

    value: AnswerValue
    follow_up_text: str | None


@dataclass(frozen=True)
class ProgressView:
    """The user's answers and the questions currently visible (branching applied)."""

    answers: dict[str, SavedAnswer]
    visible_question_ids: list[str]
    submitted: bool
    submitted_at: datetime | None


@dataclass(frozen=True)
class AnsweredQuestion:
    """A non-medical answer with its question text, for AI-facing modules (C6)."""

    question_id: str
    question_text: str
    answer_text: str


@dataclass(frozen=True)
class OnboardingState:
    """Whether consent exists and the questionnaire is submitted (for the Journey, C6)."""

    consented: bool
    submitted: bool


def _values(answers: Mapping[str, Any]) -> dict[str, AnswerValue]:
    return {question_id: entry["value"] for question_id, entry in answers.items()}


class OnboardingService:
    """Consent and questionnaire use cases. Each public method commits its own changes.

    Args:
        clock: Time source.
        consent: The configured consent text (versioned).
        definition: The active questionnaire definition (seed data).
        support_url: Optional professional-support link (AC4.3.4).
    """

    def __init__(
        self,
        *,
        clock: Clock,
        consent: ConsentText,
        definition: QuestionnaireDefinition,
        support_url: str | None = None,
    ) -> None:
        self.clock = clock
        self.consent = consent
        self.definition = definition
        self.support_url = support_url

    # --- Consent ---------------------------------------------------------------------------

    def consent_state(self, session: Session, user_id: uuid.UUID) -> ConsentView:
        """The current consent text and this user's agreement to it (US4.1)."""
        record = repositories.find_consent(session, user_id, self.consent.version)
        return ConsentView(
            version=self.consent.version,
            text=self.consent.text,
            agreement=self.consent.agreement,
            given=record is not None,
            given_at=record.given_at if record is not None else None,
        )

    def give_consent(self, session: Session, user_id: uuid.UUID, version: str) -> ConsentView:
        """Record consent to ``version`` with a timestamp (AC4.1.2).

        Raises:
            ConsentVersionChanged: When ``version`` is not the current text version.
        """
        if version != self.consent.version:
            raise ConsentVersionChanged()
        record = repositories.record_consent(session, user_id, version, self.clock.now())
        session.commit()
        logger.info(
            "consent recorded",
            extra={"event": "onboarding.consent.given", "userId": str(user_id), "version": version},
        )
        return ConsentView(
            version=version,
            text=self.consent.text,
            agreement=self.consent.agreement,
            given=True,
            given_at=record.given_at,
        )

    def require_consent(self, session: Session, user_id: uuid.UUID) -> None:
        """Refuse questionnaire actions without consent to the current text (AC4.1.1).

        Raises:
            ConsentRequired: 403 when no consent to the current version is stored.
        """
        if repositories.find_consent(session, user_id, self.consent.version) is None:
            raise ConsentRequired()

    # --- Questionnaire ---------------------------------------------------------------------

    def questionnaire(self, session: Session, user_id: uuid.UUID) -> QuestionnaireDefinition:
        """The active definition, once consent is given (US4.2, US4.4)."""
        self.require_consent(session, user_id)
        return self.definition

    def _view(self, response: QuestionnaireResponse | None) -> ProgressView:
        answers: Mapping[str, Any] = response.answers if response is not None else {}
        visible = visible_questions(self.definition, _values(answers))
        return ProgressView(
            answers={
                question_id: SavedAnswer(entry["value"], entry.get("followUpText"))
                for question_id, entry in answers.items()
            },
            visible_question_ids=[question.id for question in visible],
            submitted=response is not None and response.status == ResponseStatus.SUBMITTED,
            submitted_at=response.submitted_at if response is not None else None,
        )

    def progress(self, session: Session, user_id: uuid.UUID) -> ProgressView:
        """The user's saved answers and visible questions (resume, AC4.2.6)."""
        self.require_consent(session, user_id)
        return self._view(repositories.find_response(session, user_id))

    def _open_response(self, session: Session, user_id: uuid.UUID) -> QuestionnaireResponse:
        now = self.clock.now()
        repositories.ensure_definition_stored(session, self.definition, now)
        response = repositories.lock_response(session, user_id, self.definition.version, now)
        if response.status == ResponseStatus.SUBMITTED:
            raise QuestionnaireAlreadySubmitted()
        if response.definition_version != self.definition.version:
            # A newer definition was published: keep only answers it still asks for.
            response.answers = {
                qid: entry
                for qid, entry in response.answers.items()
                if self.definition.question(qid) is not None
            }
            response.definition_version = self.definition.version
        return response

    def save_answer(
        self,
        session: Session,
        user_id: uuid.UUID,
        question_id: str,
        value: object,
        follow_up_text: str | None,
    ) -> ProgressView:
        """Save or change one answer and return the recalculated progress (D3; AC4.2.5).

        Raises:
            ConsentRequired: Without consent to the current text.
            NotFound: For an unknown question id.
            ValidationFailed: ``QUESTION_HIDDEN`` for a question branching hides, or the
                type-specific reasons of :func:`validate_answer`.
            QuestionnaireAlreadySubmitted: After submission.
        """
        self.require_consent(session, user_id)
        question = self.definition.question(question_id)
        if question is None:
            raise NotFound("We couldn't find that question.")
        clean, follow_up = validate_answer(question, value, follow_up_text)
        response = self._open_response(session, user_id)
        answers = dict(response.answers)
        visible_ids = {q.id for q in visible_questions(self.definition, _values(answers))}
        if question_id not in visible_ids:
            raise ValidationFailed(details=[{"field": "questionId", "reason": "QUESTION_HIDDEN"}])
        now = self.clock.now()
        answers[question_id] = {
            "value": clean,
            "followUpText": follow_up,
            "questionText": question.text,
            "medical": question.medical,
            "answeredAt": now.isoformat(),
        }
        response.answers = answers  # a new dict, so the JSONB change is detected
        response.updated_at = now
        session.commit()
        return self._view(response)

    def submit(
        self, session: Session, user_id: uuid.UUID, *, disclaimer_confirmed: bool
    ) -> ProgressView:
        """Submit the questionnaire (US4.3; BR-003, re-validated on the server).

        Hidden answers (for example Q19 after Q4 changed to Feminine) are dropped.

        Raises:
            ConsentRequired: Without consent to the current text.
            ValidationFailed: ``REQUIRED`` for each unanswered required visible question.
            DisclaimerRequired: When the disclaimer is not confirmed (AC4.3.3).
            QuestionnaireAlreadySubmitted: On a second submission.
        """
        self.require_consent(session, user_id)
        response = self._open_response(session, user_id)
        answers = dict(response.answers)
        values = _values(answers)
        visible = visible_questions(self.definition, values)
        missing = [q.id for q in visible if q.required and not is_answered(q, values.get(q.id))]
        if missing:
            session.rollback()
            raise ValidationFailed(
                "Please answer every question before submitting.",
                details=[{"field": qid, "reason": "REQUIRED"} for qid in missing],
            )
        if not disclaimer_confirmed:
            session.rollback()
            raise DisclaimerRequired()
        now = self.clock.now()
        response.answers = {q.id: answers[q.id] for q in visible if q.id in answers}
        response.status = ResponseStatus.SUBMITTED.value
        response.disclaimer_accepted_at = now
        response.submitted_at = now
        response.updated_at = now
        session.commit()
        logger.info(
            "questionnaire submitted",
            extra={"event": "onboarding.questionnaire.submitted", "userId": str(user_id)},
        )
        return self._view(response)

    # --- Read ports for other modules (C6) -------------------------------------------------

    def non_medical_answers(self, session: Session, user_id: uuid.UUID) -> list[AnsweredQuestion]:
        """Submitted, non-medical answers with question text (ADR-007; D4).

        Never returns a medical-flagged answer or its follow-up (the follow-up inherits the
        flag). The flag is read from the active definition AND the stored answer, so either
        marking excludes it. Returns an empty list before submission.
        """
        response = repositories.find_response(session, user_id)
        if response is None or response.status != ResponseStatus.SUBMITTED:
            return []
        values = _values(response.answers)
        result: list[AnsweredQuestion] = []
        for question in visible_questions(self.definition, values):
            entry = response.answers.get(question.id)
            if entry is None or question.medical or entry.get("medical", True):
                continue
            follow_up = entry.get("followUpText")
            if not follow_up_visible(question, entry["value"]):
                follow_up = None
            result.append(
                AnsweredQuestion(
                    question_id=question.id,
                    question_text=question.text,
                    answer_text=answer_text(question, entry["value"], follow_up),
                )
            )
        return result

    def state(self, session: Session, user_id: uuid.UUID) -> OnboardingState:
        """Consent and submission flags for the Journey (C6 ``onboarding_state``)."""
        consented = repositories.find_consent(session, user_id, self.consent.version) is not None
        response = repositories.find_response(session, user_id)
        submitted = response is not None and response.status == ResponseStatus.SUBMITTED
        return OnboardingState(consented=consented, submitted=submitted)
