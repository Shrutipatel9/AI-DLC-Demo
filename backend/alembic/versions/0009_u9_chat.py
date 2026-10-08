"""U9 chat: the conversation and the per-day usage counter.

Revision ID: 0009_u9_chat
Revises: 0008_u8_report
Create Date: 2026-10-08

- table ``chat_messages``: one row per user or assistant message.
- table ``chat_usage``: replies counted (or in flight) per user and UTC day; the atomic upsert on
  it decides who gets the last message of the day (AC10.3.3).

Downgrade drops both tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_u9_chat"
down_revision: str | Sequence[str] | None = "0008_u8_report"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``chat_messages`` and ``chat_usage``."""
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name=op.f("ck_chat_messages_role_allowed")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_messages_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(op.f("ix_chat_messages_user_id"), "chat_messages", ["user_id"], unique=False)
    op.create_table(
        "chat_usage",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("used", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("used >= 0", name=op.f("ck_chat_usage_used_not_negative")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_usage_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "day", name=op.f("pk_chat_usage")),
    )


def downgrade() -> None:
    """Drop the chat tables."""
    op.drop_table("chat_usage")
    op.drop_index(op.f("ix_chat_messages_user_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
