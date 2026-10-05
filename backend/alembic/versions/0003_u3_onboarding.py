"""U3 onboarding: consent records, questionnaire definitions and responses.

Revision ID: 0003_u3_onboarding
Revises: 0002_u2_session_security
Create Date: 2026-10-02 00:00:00+00:00

Creates (US4.1, US4.2, US4.4; plan decisions D1-D3):
- table ``consent_records`` (unique ``user_id, consent_text_version``; index on ``user_id``);
- table ``questionnaire_definitions`` (primary key ``version``; definition as JSONB);
- table ``questionnaire_responses`` (unique ``user_id``; FK to the definition version;
  status, answers JSONB, ``disclaimer_accepted_at``, ``submitted_at``; checks that a
  submitted response has both timestamps).

The definition rows themselves are written by the seed loader
(``app.onboarding.definition.ensure_definition_stored``) from
``app/onboarding/data/questionnaire_v1.json``, not by this migration, so changing the
content never needs a schema migration (D1). Downgrade drops everything in reverse order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_u3_onboarding"
down_revision: str | Sequence[str] | None = "0002_u2_session_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the U3 tables."""
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_text_version", sa.String(length=64), nullable=False),
        sa.Column("given_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_consent_records_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_records")),
        sa.UniqueConstraint(
            "user_id",
            "consent_text_version",
            name=op.f("uq_consent_records_user_id_consent_text_version"),
        ),
    )
    op.create_index(
        op.f("ix_consent_records_user_id"), "consent_records", ["user_id"], unique=False
    )

    op.create_table(
        "questionnaire_definitions",
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("version", name=op.f("pk_questionnaire_definitions")),
    )

    op.create_table(
        "questionnaire_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "answers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("disclaimer_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('in_progress', 'submitted')",
            name=op.f("ck_questionnaire_responses_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'submitted') = (submitted_at IS NOT NULL)",
            name=op.f("ck_questionnaire_responses_submitted_at_matches"),
        ),
        sa.CheckConstraint(
            "submitted_at IS NULL OR disclaimer_accepted_at IS NOT NULL",
            name=op.f("ck_questionnaire_responses_submitted_needs_disclaimer"),
        ),
        sa.ForeignKeyConstraint(
            ["definition_version"],
            ["questionnaire_definitions.version"],
            name="fk_questionnaire_responses_definition_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_questionnaire_responses_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questionnaire_responses")),
        sa.UniqueConstraint("user_id", name=op.f("uq_questionnaire_responses_user_id")),
    )


def downgrade() -> None:
    """Drop the U3 tables in reverse order."""
    op.drop_table("questionnaire_responses")
    op.drop_table("questionnaire_definitions")
    op.drop_index(op.f("ix_consent_records_user_id"), table_name="consent_records")
    op.drop_table("consent_records")
