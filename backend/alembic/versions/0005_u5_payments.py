"""U5 payments: checkout attempts and processed webhook events.

Revision ID: 0005_u5_payments
Revises: 0004_u4_photos
Create Date: 2026-10-05 12:00:00+00:00

Creates (US6.2, US6.3, US6.4; DATA-008):
- table ``payments``: one row per checkout attempt: owner (FK users, cascade; indexed), the
  provider and its Checkout session id (unique), the configured amount (minor units, > 0) and
  currency (3 letters) at checkout time, status ``pending``/``succeeded``/``failed``, and
  timestamps. A check keeps ``succeeded`` and ``paid_at`` together.
- table ``payment_events``: each processed webhook event, keyed by the provider's event id
  (unique), so repeated or concurrent deliveries of one event change nothing twice (AC6.3.2);
  the payment it touched (FK, cascade; indexed; NULL for an unknown session).

Downgrade drops both tables in reverse order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_u5_payments"
down_revision: str | Sequence[str] | None = "0004_u4_photos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the U5 tables."""
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_session_id", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name=op.f("ck_payments_status_allowed"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payments_amount_positive")),
        sa.CheckConstraint("char_length(currency) = 3", name=op.f("ck_payments_currency_code")),
        sa.CheckConstraint(
            "(status = 'succeeded') = (paid_at IS NOT NULL)",
            name=op.f("ck_payments_paid_at_set"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_payments_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("provider_session_id", name=op.f("uq_payments_provider_session_id")),
    )
    op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"], unique=False)

    op.create_table(
        "payment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_events_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
        sa.UniqueConstraint("provider_event_id", name=op.f("uq_payment_events_provider_event_id")),
    )
    op.create_index(
        op.f("ix_payment_events_payment_id"), "payment_events", ["payment_id"], unique=False
    )


def downgrade() -> None:
    """Drop the U5 tables in reverse order."""
    op.drop_index(op.f("ix_payment_events_payment_id"), table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index(op.f("ix_payments_user_id"), table_name="payments")
    op.drop_table("payments")
