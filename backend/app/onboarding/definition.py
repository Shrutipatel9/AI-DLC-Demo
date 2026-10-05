"""Questionnaire definition and consent text: versioned data, never code (D1, D2; FR4.2).

The definition (questions, types, options, branching rules, follow-ups, medical flags and
the disclaimer text) is read from a JSON seed file and validated here (the seed loader),
then stored once per version in ``questionnaire_definitions`` by
``repositories.ensure_definition_stored``. Changing
questions means publishing a new file with a new ``version``; a stored version is immutable.

Pure functions in this module:
- :func:`visible_questions` evaluates branching (``showIf``) in question order (US4.2);
- :func:`validate_answer` checks one answer against its question type (D3);
- :func:`answer_text` renders an answer as plain text for the public read port (D4).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, model_validator
from pydantic.alias_generators import to_camel

from app.platform.errors import ValidationFailed

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_QUESTIONNAIRE_FILE = DATA_DIR / "questionnaire_v1.json"
DEFAULT_CONSENT_FILE = DATA_DIR / "consent_v1.json"

QuestionType = Literal["text", "single", "multi", "yesno"]
#: A stored answer value: text and single choice are strings, multi-select is a list of
#: option values, Yes/No is a boolean.
AnswerValue = str | bool | list[str]
Scalar = StrictStr | StrictBool

DEFAULT_TEXT_MAX_LENGTH = 500
FOLLOW_UP_MAX_LENGTH = 2000


class DefinitionError(ValueError):
    """A seed file is malformed, or a stored version differs from its file."""


class _DataModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)


class Option(_DataModel):
    """One choice of a single- or multi-select question. ``group`` is a visual heading."""

    model_config = ConfigDict(extra="forbid")

    value: Annotated[str, Field(min_length=1, max_length=64)]
    label: Annotated[str, Field(min_length=1, max_length=200)]
    group: str | None = None


class FollowUp(_DataModel):
    """A free-text field revealed when the parent's answer equals ``show_when`` (AC4.2.4)."""

    model_config = ConfigDict(extra="forbid")

    show_when: Scalar
    type: Literal["text"] = "text"
    label: Annotated[str, Field(min_length=1, max_length=200)]
    max_length: Annotated[int, Field(gt=0, le=FOLLOW_UP_MAX_LENGTH)] = FOLLOW_UP_MAX_LENGTH


class ShowIf(_DataModel):
    """Branching rule: show the question only when ``question_id``'s answer is in ``any_of``."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    any_of: Annotated[tuple[Scalar, ...], Field(min_length=1)]


class Question(_DataModel):
    """One questionnaire question. ``medical`` is server-side only (ADR-007)."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
    order: Annotated[int, Field(ge=1)]
    text: Annotated[str, Field(min_length=1, max_length=500)]
    type: QuestionType
    required: bool = True
    medical: bool = False
    placeholder: str | None = None
    max_length: Annotated[int, Field(gt=0, le=FOLLOW_UP_MAX_LENGTH)] = DEFAULT_TEXT_MAX_LENGTH
    options: tuple[Option, ...] = ()
    follow_up: FollowUp | None = None
    show_if: ShowIf | None = None
    #: Open items for the client (D5). Never sent to the browser.
    note: str | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> Question:
        choice = self.type in ("single", "multi")
        if choice and not self.options:
            raise ValueError(f"{self.id}: a {self.type} question needs options")
        if not choice and self.options:
            raise ValueError(f"{self.id}: only single and multi questions have options")
        values = [option.value for option in self.options]
        if len(values) != len(set(values)):
            raise ValueError(f"{self.id}: option values must be unique")
        if self.follow_up is not None and not self.accepts(self.follow_up.show_when):
            raise ValueError(f"{self.id}: followUp.showWhen is not a possible answer")
        return self

    def accepts(self, value: object) -> bool:
        """Whether ``value`` is a possible scalar answer (used by branching rules)."""
        if self.type == "yesno":
            return isinstance(value, bool)
        if self.type in ("single", "multi"):
            return isinstance(value, str) and value in self.option_values
        return isinstance(value, str)

    @property
    def option_values(self) -> frozenset[str]:
        """The allowed option values."""
        return frozenset(option.value for option in self.options)

    def option_label(self, value: str) -> str:
        """The label for an option value (the value itself when unknown)."""
        for option in self.options:
            if option.value == value:
                return option.label
        return value


class QuestionnaireDefinition(_DataModel):
    """A complete, validated definition version (D1)."""

    model_config = ConfigDict(extra="forbid")

    version: Annotated[str, Field(min_length=1, max_length=64)]
    source: str | None = None
    notes: tuple[str, ...] = ()
    disclaimer_text: Annotated[str, Field(min_length=1)]
    questions: Annotated[tuple[Question, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _check_questions(self) -> QuestionnaireDefinition:
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique")
        orders = [question.order for question in self.questions]
        if orders != sorted(orders) or len(orders) != len(set(orders)):
            raise ValueError("questions must be listed in strictly increasing order")
        seen: dict[str, Question] = {}
        for question in self.questions:
            rule = question.show_if
            if rule is not None:
                parent = seen.get(rule.question_id)
                if parent is None:
                    raise ValueError(f"{question.id}: showIf must refer to an earlier question")
                if parent.type == "multi" or not all(parent.accepts(v) for v in rule.any_of):
                    raise ValueError(f"{question.id}: showIf values must be answers of its parent")
            seen[question.id] = question
        return self

    def question(self, question_id: str) -> Question | None:
        """Find a question by id."""
        for question in self.questions:
            if question.id == question_id:
                return question
        return None

    def stored_form(self) -> dict[str, Any]:
        """The JSON stored in ``questionnaire_definitions.definition``."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class ConsentText(_DataModel):
    """The versioned consent text shown before the questionnaire (D2; AC4.1.3)."""

    model_config = ConfigDict(extra="forbid")

    version: Annotated[str, Field(min_length=1, max_length=64)]
    text: Annotated[str, Field(min_length=1)]
    agreement: Annotated[str, Field(min_length=1)]
    note: str | None = None


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DefinitionError(f"Cannot read {path.name}: {type(exc).__name__}") from exc


def load_definition(path: Path = DEFAULT_QUESTIONNAIRE_FILE) -> QuestionnaireDefinition:
    """Load and validate a questionnaire seed file (the seed loader, D1).

    Raises:
        DefinitionError: When the file is missing, not JSON, or breaks a rule.
    """
    try:
        return QuestionnaireDefinition.model_validate(_read_json(path))
    except ValueError as exc:
        if isinstance(exc, DefinitionError):
            raise
        raise DefinitionError(f"Invalid questionnaire definition {path.name}: {exc}") from exc


def load_consent_text(path: Path = DEFAULT_CONSENT_FILE) -> ConsentText:
    """Load and validate the consent text file (D2).

    Raises:
        DefinitionError: When the file is missing, not JSON, or breaks a rule.
    """
    try:
        return ConsentText.model_validate(_read_json(path))
    except ValueError as exc:
        if isinstance(exc, DefinitionError):
            raise
        raise DefinitionError(f"Invalid consent text {path.name}: {exc}") from exc


# --- Branching ---------------------------------------------------------------------------


def visible_questions(
    definition: QuestionnaireDefinition, values: Mapping[str, AnswerValue]
) -> list[Question]:
    """The questions to show, in order, given the answers so far (US4.2; AC4.4.2).

    A question with ``showIf`` is shown only when its parent is itself shown and the
    parent's answer is one of ``anyOf``. An unanswered parent hides the dependant.
    """
    shown: list[Question] = []
    shown_ids: set[str] = set()
    for question in definition.questions:
        rule = question.show_if
        if rule is not None:
            parent_value = values.get(rule.question_id)
            if rule.question_id not in shown_ids or parent_value not in rule.any_of:
                continue
        shown.append(question)
        shown_ids.add(question.id)
    return shown


def follow_up_visible(question: Question, value: AnswerValue | None) -> bool:
    """Whether the question's follow-up field is revealed by ``value``."""
    return question.follow_up is not None and value == question.follow_up.show_when


# --- Answer validation --------------------------------------------------------------------


def _invalid(reason: str, field: str = "value") -> ValidationFailed:
    return ValidationFailed(details=[{"field": field, "reason": reason}])


def _validate_value(question: Question, value: object) -> AnswerValue:
    if question.type == "yesno":
        if not isinstance(value, bool):
            raise _invalid("WRONG_TYPE")
        return value
    if question.type == "multi":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise _invalid("WRONG_TYPE")
        if len(value) != len(set(value)):
            raise _invalid("DUPLICATE_OPTION")
        if any(item not in question.option_values for item in value):
            raise _invalid("NOT_AN_OPTION")
        if question.required and not value:
            raise _invalid("REQUIRED")
        return list(value)
    if not isinstance(value, str):
        raise _invalid("WRONG_TYPE")
    if question.type == "single":
        if value not in question.option_values:
            raise _invalid("NOT_AN_OPTION")
        return value
    text = value.strip()
    if question.required and not text:
        raise _invalid("REQUIRED")
    if len(text) > question.max_length:
        raise _invalid("TOO_LONG")
    return text


def validate_answer(
    question: Question, value: object, follow_up_text: str | None
) -> tuple[AnswerValue, str | None]:
    """Check one answer against its question and normalise it (D3).

    The follow-up text is kept only while the answer reveals the follow-up; otherwise it is
    dropped, so a hidden follow-up is never stored.

    Raises:
        ValidationFailed: With ``field`` (``value`` or ``followUpText``) and a ``reason``:
            ``WRONG_TYPE``, ``NOT_AN_OPTION``, ``DUPLICATE_OPTION``, ``REQUIRED`` or
            ``TOO_LONG``.
    """
    clean = _validate_value(question, value)
    if not follow_up_visible(question, clean) or follow_up_text is None:
        return clean, None
    assert question.follow_up is not None  # noqa: S101  (narrowed by follow_up_visible)
    text = follow_up_text.strip()
    if len(text) > question.follow_up.max_length:
        raise _invalid("TOO_LONG", "followUpText")
    return clean, text or None


def is_answered(question: Question, value: AnswerValue | None) -> bool:
    """Whether a stored value satisfies the question's ``required`` flag."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) or not question.required
    if isinstance(value, list):
        return bool(value) or not question.required
    return True


def answer_text(question: Question, value: AnswerValue, follow_up_text: str | None) -> str:
    """Render an answer as plain text, with option labels instead of values (D4)."""
    if isinstance(value, bool):
        rendered = "Yes" if value else "No"
    elif isinstance(value, list):
        rendered = "; ".join(question.option_label(item) for item in value) or "None selected"
    elif question.type == "single":
        rendered = question.option_label(value)
    else:
        rendered = value
    if follow_up_text:
        rendered = f"{rendered} — {follow_up_text}"
    return rendered
