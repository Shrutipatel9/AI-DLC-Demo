"""U2 session security: reset tokens, shadow counters, refresh-session lifecycle columns.

Revision ID: 0002_u2_session_security
Revises: 0001_u1_identity
Create Date: 2026-10-02 00:00:00+00:00

Creates (U2 NFR design post-review R-10, performance design section 2):
- table ``password_reset_tokens`` (``token_hash`` unique; index on ``user_id``);
- table ``email_attempt_counters`` (primary key ``email_hash, purpose``);
- column ``verification_attempts.flow_started_at``;
- columns ``refresh_sessions.revoked_reason`` (with checks) and ``refresh_sessions.attempt_hash``;
- index ``refresh_sessions(parent_token_id)`` for the child lookup on recovery;
- partial index ``refresh_sessions(user_id) WHERE revoked_at IS NULL AND rotated_at IS NULL``
  for the revocations on reset and change.

``refresh_sessions.parent_token_id`` already has ``ON DELETE SET NULL`` since 0001, so the
"FK change" listed in R-10 needs no statement here. ``refresh_sessions(family_id)`` is
also indexed since 0001. Downgrade drops everything in reverse order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_u2_session_security"
down_revision: str | Sequence[str] | None = "0001_u1_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PURPOSES = "purpose IN ('signup', 'login', 'password_reset')"
REASONS = (
    "revoked_reason IS NULL OR revoked_reason IN "
    "('logout', 'reuse_detected', 'password_reset', 'password_changed')"
)


def upgrade() -> None:
    """Create the U2 tables, columns and indexes."""
    op.create_table(
        "password_reset_tokens",
        sa.Column("reset_token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("reset_token_id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "email_attempt_counters",
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flow_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "failed_count >= 0", name=op.f("ck_email_attempt_counters_failed_count_non_negative")
        ),
        sa.CheckConstraint(PURPOSES, name=op.f("ck_email_attempt_counters_purpose_allowed")),
        sa.PrimaryKeyConstraint("email_hash", "purpose", name=op.f("pk_email_attempt_counters")),
    )

    op.add_column(
        "verification_attempts",
        sa.Column("flow_started_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "refresh_sessions", sa.Column("revoked_reason", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "refresh_sessions", sa.Column("attempt_hash", sa.String(length=64), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_refresh_sessions_revoked_reason_allowed"), "refresh_sessions", REASONS
    )
    op.create_check_constraint(
        op.f("ck_refresh_sessions_revoked_reason_with_time"),
        "refresh_sessions",
        "(revoked_at IS NULL) = (revoked_reason IS NULL)",
    )
    op.create_index(
        op.f("ix_refresh_sessions_parent_token_id"),
        "refresh_sessions",
        ["parent_token_id"],
        unique=False,
    )
    op.create_index(
        "ix_refresh_sessions_user_id_usable",
        "refresh_sessions",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL AND rotated_at IS NULL"),
    )


def downgrade() -> None:
    """Drop the U2 schema additions in reverse order."""
    op.drop_index("ix_refresh_sessions_user_id_usable", table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_parent_token_id"), table_name="refresh_sessions")
    op.drop_constraint(
        op.f("ck_refresh_sessions_revoked_reason_with_time"), "refresh_sessions", type_="check"
    )
    op.drop_constraint(
        op.f("ck_refresh_sessions_revoked_reason_allowed"), "refresh_sessions", type_="check"
    )
    op.drop_column("refresh_sessions", "attempt_hash")
    op.drop_column("refresh_sessions", "revoked_reason")
    op.drop_column("verification_attempts", "flow_started_at")
    op.drop_table("email_attempt_counters")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
