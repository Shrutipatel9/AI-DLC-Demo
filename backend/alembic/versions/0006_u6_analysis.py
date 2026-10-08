"""U6 analysis core: background jobs and analysis runs.

Revision ID: 0006_u6_analysis
Revises: 0005_u5_payments
Create Date: 2026-10-07 09:00:00+00:00

Creates (US1.7, US7.1, US7.6, US7.9, US7.11):
- table ``jobs``: the PostgreSQL job queue (kind, id-only payload, status, current step,
  small result, failure reason, attempts, worker id, heartbeat); indexed by status and age
  for ``FOR UPDATE SKIP LOCKED`` claiming.
- table ``analysis_runs``: one run per payment (unique ``payment_id``), its job, status,
  whether the one free re-run was used, the failure count and reason.
- table ``analysis_run_photos``: the photo files the run was started with (R-02).
- table ``analysis_steps``: the four named steps and their saved outputs.
- table ``analysis_results``: the stored analysis result, one per run.
- table ``analysis_image_slots``: the 24 image slots (filled by U7).

Downgrade drops the tables in reverse order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_u6_analysis"
down_revision: str | Sequence[str] | None = "0005_u5_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the U6 tables."""
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_step", sa.String(length=64), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name=op.f("ck_jobs_status_allowed"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_jobs_attempts_not_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"], unique=False)

    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rerun_used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_step", sa.String(length=32), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name=op.f("ck_analysis_runs_status_allowed"),
        ),
        sa.CheckConstraint(
            "failure_count >= 0", name=op.f("ck_analysis_runs_failure_count_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_analysis_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_analysis_runs_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_analysis_runs_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
        sa.UniqueConstraint("payment_id", name=op.f("uq_analysis_runs_payment_id")),
    )
    op.create_index(op.f("ix_analysis_runs_user_id"), "analysis_runs", ["user_id"], unique=False)

    op.create_table(
        "analysis_run_photos",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("angle", sa.String(length=32), nullable=False),
        sa.Column("media_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_run_photos_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_file_id"],
            ["media_files.id"],
            name=op.f("fk_analysis_run_photos_media_file_id_media_files"),
            ondelete="NO ACTION",
        ),
        sa.PrimaryKeyConstraint("run_id", "angle", name=op.f("pk_analysis_run_photos")),
    )
    op.create_index(
        op.f("ix_analysis_run_photos_media_file_id"),
        "analysis_run_photos",
        ["media_file_id"],
        unique=False,
    )

    op.create_table(
        "analysis_steps",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('waiting', 'done', 'failed')",
            name=op.f("ck_analysis_steps_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_steps_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "key", name=op.f("pk_analysis_steps")),
    )

    op.create_table(
        "analysis_results",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_results_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_analysis_results_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_analysis_results")),
    )
    op.create_index(
        op.f("ix_analysis_results_user_id"), "analysis_results", ["user_id"], unique=False
    )

    op.create_table(
        "analysis_image_slots",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_key", sa.String(length=32), nullable=False),
        sa.Column("slot_kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_image_slots_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "slot_key", name=op.f("pk_analysis_image_slots")),
    )


def downgrade() -> None:
    """Drop the U6 tables."""
    op.drop_table("analysis_image_slots")
    op.drop_index(op.f("ix_analysis_results_user_id"), table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_table("analysis_steps")
    op.drop_index(op.f("ix_analysis_run_photos_media_file_id"), table_name="analysis_run_photos")
    op.drop_table("analysis_run_photos")
    op.drop_index(op.f("ix_analysis_runs_user_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_table("jobs")
