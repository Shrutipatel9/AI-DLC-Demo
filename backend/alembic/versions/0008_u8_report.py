"""U8 report: the cached report PDF and its media kind.

Revision ID: 0008_u8_report
Revises: 0007_u7_images
Create Date: 2026-10-08

- table ``report_pdfs``: one row per run; the cached PDF (a private MediaStore file) and the
  fingerprint of what it was built from, so a changed image regenerates it (AC8.5.3).
- ``media_files.kind`` also allows ``report_pdf``.

Downgrade drops the table and the kind (PDF file rows are deleted first).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_u8_report"
down_revision: str | Sequence[str] | None = "0007_u7_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``report_pdfs`` and widen the media kind check."""
    op.drop_constraint(op.f("ck_media_files_kind_allowed"), "media_files", type_="check")
    op.create_check_constraint(
        op.f("ck_media_files_kind_allowed"),
        "media_files",
        "kind IN ('photo', 'ai_image', 'report_pdf')",
    )
    op.create_table(
        "report_pdfs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_report_pdfs_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_pdfs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_file_id"],
            ["media_files.id"],
            name=op.f("fk_report_pdfs_media_file_id_media_files"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_report_pdfs")),
    )
    op.create_index(op.f("ix_report_pdfs_user_id"), "report_pdfs", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop ``report_pdfs`` and narrow the media kind check."""
    op.drop_index(op.f("ix_report_pdfs_user_id"), table_name="report_pdfs")
    op.drop_table("report_pdfs")
    op.execute("DELETE FROM media_files WHERE kind = 'report_pdf'")
    op.drop_constraint(op.f("ck_media_files_kind_allowed"), "media_files", type_="check")
    op.create_check_constraint(
        op.f("ck_media_files_kind_allowed"), "media_files", "kind IN ('photo', 'ai_image')"
    )
