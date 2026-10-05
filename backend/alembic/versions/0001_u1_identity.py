"""U1 identity schema: users, one-time codes, attempt counters, refresh sessions, limiter.

Revision ID: 0001_u1_identity
Revises:
Create Date: 2026-10-01 00:00:00+00:00

Indexes follow performance design section 2:
- users(lower(email)) unique;
- one_time_codes(user_id, purpose) unique WHERE consumed_at IS NULL AND superseded_at IS NULL;
- verification_attempts primary key (user_id, purpose);
- refresh_sessions(token_id) primary key;
- rate_limit_hits(key, hit_at).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_u1_identity"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PURPOSES = "purpose IN ('signup', 'login', 'password_reset')"


def upgrade() -> None:
    """Create the U1 tables."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user')", name=op.f("ck_users_role_allowed")),
        sa.CheckConstraint(
            "(verified_at IS NOT NULL) = is_verified",
            name=op.f("ck_users_verified_at_matches_flag"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )

    op.create_table(
        "one_time_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(PURPOSES, name=op.f("ck_one_time_codes_purpose_allowed")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_one_time_codes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_one_time_codes")),
    )
    op.create_index(
        "uq_one_time_codes_live",
        "one_time_codes",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL AND superseded_at IS NULL"),
    )

    op.create_table(
        "verification_attempts",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "failed_count >= 0", name=op.f("ck_verification_attempts_failed_count_non_negative")
        ),
        sa.CheckConstraint(PURPOSES, name=op.f("ck_verification_attempts_purpose_allowed")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_verification_attempts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "purpose", name=op.f("pk_verification_attempts")),
    )

    op.create_table(
        "refresh_sessions",
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_token_id"],
            ["refresh_sessions.token_id"],
            name=op.f("fk_refresh_sessions_parent_token_id_refresh_sessions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token_id", name=op.f("pk_refresh_sessions")),
    )
    op.create_index(
        op.f("ix_refresh_sessions_family_id"), "refresh_sessions", ["family_id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_sessions_user_id"), "refresh_sessions", ["user_id"], unique=False
    )

    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("hit_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_hits")),
    )
    op.create_index(
        "ix_rate_limit_hits_key_hit_at", "rate_limit_hits", ["key", "hit_at"], unique=False
    )


def downgrade() -> None:
    """Drop the U1 tables (reverse order)."""
    op.drop_index("ix_rate_limit_hits_key_hit_at", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
    op.drop_index(op.f("ix_refresh_sessions_user_id"), table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_family_id"), table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_table("verification_attempts")
    op.drop_index("uq_one_time_codes_live", table_name="one_time_codes")
    op.drop_table("one_time_codes")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
