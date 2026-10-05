"""Onboarding HTTP routes (contract C1 ``/onboarding/*``; US4.1-US4.4).

Every route is protected: the app factory mounts this router with ``current_user``, and
each handler also takes the caller from ``current_user`` (cached per request), so a user
only ever reads and writes their own consent and answers (BR6.2). Handlers stay thin and
call :class:`OnboardingService`; they never touch repositories or models.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.onboarding.definition import QuestionnaireDefinition
from app.onboarding.dependencies import get_onboarding, no_store
from app.onboarding.schemas import (
    AnswerInput,
    ConsentRequest,
    ConsentState,
    FollowUpOut,
    OptionOut,
    QuestionnaireDefinitionOut,
    QuestionnaireProgress,
    QuestionOut,
    SavedAnswerOut,
    ShowIfOut,
    SubmitRequest,
)
from app.onboarding.services import ConsentView, OnboardingService, ProgressView
from app.platform.db import get_session
from app.platform.errors import error_responses

SessionDep = Annotated[Session, Depends(get_session)]
OnboardingDep = Annotated[OnboardingService, Depends(get_onboarding)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
QuestionIdPath = Annotated[
    str, Path(alias="questionId", min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
]

router = APIRouter(tags=["onboarding"], dependencies=[Depends(no_store)])


def _consent(view: ConsentView) -> ConsentState:
    return ConsentState(
        consent_text_version=view.version,
        consent_text=view.text,
        agreement_text=view.agreement,
        given=view.given,
        given_at=view.given_at,
    )


def _definition(
    definition: QuestionnaireDefinition, support_url: str | None
) -> QuestionnaireDefinitionOut:
    questions = [
        QuestionOut(
            id=q.id,
            order=q.order,
            text=q.text,
            type=q.type,
            required=q.required,
            placeholder=q.placeholder,
            max_length=q.max_length if q.type == "text" else None,
            options=[OptionOut(value=o.value, label=o.label, group=o.group) for o in q.options],
            follow_up=(
                FollowUpOut(
                    show_when=q.follow_up.show_when,
                    label=q.follow_up.label,
                    max_length=q.follow_up.max_length,
                )
                if q.follow_up is not None
                else None
            ),
            show_if=(
                ShowIfOut(question_id=q.show_if.question_id, any_of=list(q.show_if.any_of))
                if q.show_if is not None
                else None
            ),
        )
        for q in definition.questions
    ]
    return QuestionnaireDefinitionOut(
        definition_version=definition.version,
        disclaimer_text=definition.disclaimer_text,
        support_url=support_url,
        questions=questions,
    )


def _progress(view: ProgressView) -> QuestionnaireProgress:
    return QuestionnaireProgress(
        answers={
            question_id: SavedAnswerOut(value=answer.value, follow_up_text=answer.follow_up_text)
            for question_id, answer in view.answers.items()
        },
        visible_question_ids=view.visible_question_ids,
        submitted=view.submitted,
        submitted_at=view.submitted_at,
    )


@router.get(
    "/onboarding/consent",
    response_model=ConsentState,
    response_model_by_alias=True,
    responses=error_responses(401),
    summary="Current consent text and whether the user has consented (FR4.1)",
)
def get_consent(user: UserDep, session: SessionDep, onboarding: OnboardingDep) -> ConsentState:
    """Return the configured consent text and this user's consent to it."""
    return _consent(onboarding.consent_state(session, user.user_id))


@router.post(
    "/onboarding/consent",
    status_code=status.HTTP_201_CREATED,
    response_model=ConsentState,
    response_model_by_alias=True,
    responses=error_responses(401, 409, 422),
    summary="Records consent to the given text version (FR4.1)",
)
def post_consent(
    body: ConsentRequest, user: UserDep, session: SessionDep, onboarding: OnboardingDep
) -> ConsentState:
    """Store consent with its timestamp and text version (AC4.1.2)."""
    return _consent(onboarding.give_consent(session, user.user_id, body.consent_text_version))


@router.get(
    "/onboarding/questionnaire",
    response_model=QuestionnaireDefinitionOut,
    response_model_by_alias=True,
    response_model_exclude_none=True,
    responses=error_responses(401, 403),
    summary="The active questionnaire definition (questions, options, branching, disclaimer)",
)
def get_questionnaire(
    user: UserDep, session: SessionDep, onboarding: OnboardingDep
) -> QuestionnaireDefinitionOut:
    """Return the definition; refused with CONSENT_REQUIRED before consent (AC4.1.1)."""
    definition = onboarding.questionnaire(session, user.user_id)
    return _definition(definition, onboarding.support_url)


@router.get(
    "/onboarding/response",
    response_model=QuestionnaireProgress,
    response_model_by_alias=True,
    responses=error_responses(401, 403),
    summary="The user's saved answers and progress",
)
def get_response(
    user: UserDep, session: SessionDep, onboarding: OnboardingDep
) -> QuestionnaireProgress:
    """Return saved answers and the visible questions, to resume (AC4.2.6)."""
    return _progress(onboarding.progress(session, user.user_id))


@router.put(
    "/onboarding/response/answers/{questionId}",
    response_model=QuestionnaireProgress,
    response_model_by_alias=True,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Saves or changes one answer; returns the recalculated visible questions",
)
def put_answer(
    question_id: QuestionIdPath,
    body: AnswerInput,
    user: UserDep,
    session: SessionDep,
    onboarding: OnboardingDep,
) -> QuestionnaireProgress:
    """Save one answer (D3); branching is recalculated (AC4.2.2, AC4.2.3, AC4.2.5)."""
    view = onboarding.save_answer(
        session, user.user_id, question_id, body.value, body.follow_up_text
    )
    return _progress(view)


@router.post(
    "/onboarding/response/submit",
    response_model=QuestionnaireProgress,
    response_model_by_alias=True,
    responses=error_responses(401, 403, 409, 422),
    summary="Submits the questionnaire; refused without the disclaimer (BR-003)",
)
def submit(
    body: SubmitRequest, user: UserDep, session: SessionDep, onboarding: OnboardingDep
) -> QuestionnaireProgress:
    """Submit; 422 VALIDATION_FAILED or DISCLAIMER_REQUIRED when not ready (US4.3)."""
    view = onboarding.submit(session, user.user_id, disclaimer_confirmed=body.disclaimer_confirmed)
    return _progress(view)
