"""Onboarding ORM models (domain-design ``components.md`` Onboarding entities; migration 0003).

Tables:
- ``consent_records``: one row per (user, consent text version) the user agreed to (FR4.1);
- ``questionnaire_definitions``: each published definition version as JSON (D1);
- ``questionnaire_responses``: at most one per user, answers as JSON keyed by question id,
  each answer carrying its question text and medical flag (AC4.2.7).

These models never leave the onboarding module (ADR-007).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class ResponseStatus(StrEnum):
    """Lifecycle of a questionnaire response."""

    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"


_STATUSES = "', '".join(status.value for status in ResponseStatus)


class ConsentRecord(Base):
    """Explicit consent to one version of the consent text (AC4.1.2)."""

    __tablename__ = "consent_records"
    __table_args__ = (UniqueConstraint("user_id", "consent_text_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    consent_text_version: Mapped[str] = mapped_column(String(64))
    given_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionnaireDefinitionRecord(Base):
    """A published questionnaire definition. A version is immutable once stored (D1)."""

    __tablename__ = "questionnaire_definitions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionnaireResponse(Base):
    """A user's answers. ``answers`` maps question id to the stored answer (AC4.2.7)."""

    __tablename__ = "questionnaire_responses"
    __table_args__ = (
        CheckConstraint(f"status IN ('{_STATUSES}')", name="status_allowed"),
        CheckConstraint(
            "(status = 'submitted') = (submitted_at IS NOT NULL)", name="submitted_at_matches"
        ),
        CheckConstraint(
            "submitted_at IS NULL OR disclaimer_accepted_at IS NOT NULL",
            name="submitted_needs_disclaimer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    definition_version: Mapped[str] = mapped_column(
        String(64),
        # Named explicitly: the conventional name would exceed PostgreSQL's 63 characters.
        ForeignKey(
            "questionnaire_definitions.version",
            ondelete="RESTRICT",
            name="fk_questionnaire_responses_definition_version",
        ),
    )
    status: Mapped[str] = mapped_column(String(20), default=ResponseStatus.IN_PROGRESS.value)
    answers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    disclaimer_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
