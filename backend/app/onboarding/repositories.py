"""Onboarding data access: consent records, definition versions and responses.

Repositories never commit; the calling service owns the transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.onboarding.definition import DefinitionError, QuestionnaireDefinition
from app.onboarding.models import (
    ConsentRecord,
    QuestionnaireDefinitionRecord,
    QuestionnaireResponse,
    ResponseStatus,
)

# --- Consent ---------------------------------------------------------------------------------


def find_consent(session: Session, user_id: uuid.UUID, version: str) -> ConsentRecord | None:
    """The user's consent to ``version``, if given."""
    return session.scalars(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user_id, ConsentRecord.consent_text_version == version
        )
    ).one_or_none()


def record_consent(
    session: Session, user_id: uuid.UUID, version: str, now: datetime
) -> ConsentRecord:
    """Store consent to ``version`` once; a repeat keeps the first timestamp (idempotent)."""
    session.execute(
        pg_insert(ConsentRecord)
        .values(id=uuid.uuid4(), user_id=user_id, consent_text_version=version, given_at=now)
        .on_conflict_do_nothing(index_elements=["user_id", "consent_text_version"])
    )
    return session.scalars(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user_id, ConsentRecord.consent_text_version == version
        )
    ).one()


# --- Definitions -----------------------------------------------------------------------------


def ensure_definition_stored(
    session: Session, definition: QuestionnaireDefinition, now: datetime
) -> None:
    """Store the definition version if it is new; refuse a changed copy of a stored version.

    Idempotent and safe under concurrency (``INSERT ... ON CONFLICT DO NOTHING``).

    Raises:
        DefinitionError: When the stored version's content differs from the seed file.
    """
    stored_form = definition.stored_form()
    session.execute(
        pg_insert(QuestionnaireDefinitionRecord)
        .values(version=definition.version, definition=stored_form, created_at=now)
        .on_conflict_do_nothing(index_elements=["version"])
    )
    stored: dict[str, Any] = session.scalars(
        select(QuestionnaireDefinitionRecord.definition).where(
            QuestionnaireDefinitionRecord.version == definition.version
        )
    ).one()
    if stored != stored_form:
        raise DefinitionError(
            f"Questionnaire version {definition.version} is already stored with different "
            "content. Publish the change under a new version."
        )


# --- Responses -------------------------------------------------------------------------------


def find_response(session: Session, user_id: uuid.UUID) -> QuestionnaireResponse | None:
    """The user's questionnaire response, if one was started."""
    return session.scalars(
        select(QuestionnaireResponse).where(QuestionnaireResponse.user_id == user_id)
    ).one_or_none()


def lock_response(
    session: Session, user_id: uuid.UUID, definition_version: str, now: datetime
) -> QuestionnaireResponse:
    """Create the user's response if missing, then lock it ``FOR UPDATE``.

    ``INSERT ... ON CONFLICT DO NOTHING`` first, so two concurrent first saves cannot collide
    on the unique ``user_id``; the lock serialises concurrent answer saves.
    """
    session.execute(
        pg_insert(QuestionnaireResponse)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            definition_version=definition_version,
            status=ResponseStatus.IN_PROGRESS.value,
            answers={},
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    return session.scalars(
        select(QuestionnaireResponse)
        .where(QuestionnaireResponse.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
