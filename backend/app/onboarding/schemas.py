"""Request and response models for ``/onboarding/*`` (contract C1; camelCase JSON).

The medical flag and the client open-item notes are NOT part of any response (ADR-007).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr
from pydantic.alias_generators import to_camel

from app.onboarding.definition import FOLLOW_UP_MAX_LENGTH


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class ConsentState(CamelModel):
    """``GET/POST /onboarding/consent`` response."""

    consent_text_version: str
    consent_text: str
    #: The checkbox statement (additive to C1; configured with the consent text).
    agreement_text: str
    given: bool
    given_at: datetime | None = None


class ConsentRequest(CamelModel):
    """``POST /onboarding/consent`` body: the version the user read."""

    consent_text_version: Annotated[str, Field(min_length=1, max_length=64)]


class OptionOut(CamelModel):
    """One option of a choice question."""

    value: str
    label: str
    group: str | None = None


class FollowUpOut(CamelModel):
    """A follow-up text field revealed by ``showWhen``."""

    show_when: StrictStr | StrictBool
    type: Literal["text"] = "text"
    label: str
    max_length: int


class ShowIfOut(CamelModel):
    """Branching rule: shown when ``questionId``'s answer is one of ``anyOf``."""

    question_id: str
    any_of: list[StrictStr | StrictBool]


class QuestionOut(CamelModel):
    """One question as the browser sees it (no medical flag)."""

    id: str
    order: int
    text: str
    type: Literal["text", "single", "multi", "yesno"]
    required: bool
    placeholder: str | None = None
    max_length: int | None = None
    options: list[OptionOut] = Field(default_factory=list)
    follow_up: FollowUpOut | None = None
    show_if: ShowIfOut | None = None


class QuestionnaireDefinitionOut(CamelModel):
    """``GET /onboarding/questionnaire`` response."""

    definition_version: str
    disclaimer_text: str
    #: Optional professional-support link for the supportive message (AC4.3.4; additive).
    support_url: str | None = None
    questions: list[QuestionOut]


_AnswerText = Annotated[StrictStr, Field(max_length=FOLLOW_UP_MAX_LENGTH)]
_OptionList = Annotated[list[Annotated[StrictStr, Field(max_length=64)]], Field(max_length=50)]
AnswerValueIn = Annotated[
    _AnswerText | StrictBool | _OptionList,
    Field(description="string | string[] | boolean depending on the question type"),
]


class AnswerInput(CamelModel):
    """``PUT /onboarding/response/answers/{questionId}`` body."""

    value: AnswerValueIn
    follow_up_text: Annotated[str, Field(max_length=FOLLOW_UP_MAX_LENGTH)] | None = None


class SavedAnswerOut(CamelModel):
    """One saved answer."""

    value: StrictStr | StrictBool | list[StrictStr]
    follow_up_text: str | None = None


class QuestionnaireProgress(CamelModel):
    """The user's answers and the visible questions (branching applied)."""

    answers: dict[str, SavedAnswerOut]
    visible_question_ids: list[str]
    submitted: bool
    submitted_at: datetime | None = None


class SubmitRequest(CamelModel):
    """``POST /onboarding/response/submit`` body. Missing means not confirmed (BR-003)."""

    disclaimer_confirmed: bool = False
