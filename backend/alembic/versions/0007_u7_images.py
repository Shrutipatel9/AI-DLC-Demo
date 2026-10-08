"""U7 AI images: generated-image columns on the image slots, and the ``ai_image`` file kind.

Revision ID: 0007_u7_images
Revises: 0006_u6_analysis
Create Date: 2026-10-08

- ``analysis_image_slots``: ``media_file_id`` (the stored image), ``auto_attempts`` and
  ``manual_retries`` (AC9.5.1-AC9.5.4) and ``updated_at``.
- ``media_files.kind`` also allows ``ai_image``.

Downgrade removes the columns and the kind (generated image rows are deleted first).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_u7_images"
down_revision: str | Sequence[str] | None = "0006_u6_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the U7 columns and widen the media kind check."""
    op.add_column(
        "analysis_image_slots",
        sa.Column("media_file_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "analysis_image_slots",
        sa.Column("auto_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "analysis_image_slots",
        sa.Column("manual_retries", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "analysis_image_slots",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_analysis_image_slots_media_file_id_media_files"),
        "analysis_image_slots",
        "media_files",
        ["media_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_analysis_image_slots_media_file_id"),
        "analysis_image_slots",
        ["media_file_id"],
        unique=False,
    )
    op.drop_constraint(op.f("ck_media_files_kind_allowed"), "media_files", type_="check")
    op.create_check_constraint(
        op.f("ck_media_files_kind_allowed"), "media_files", "kind IN ('photo', 'ai_image')"
    )


def downgrade() -> None:
    """Remove the U7 columns and the ``ai_image`` kind."""
    op.execute("UPDATE analysis_image_slots SET media_file_id = NULL")
    op.execute("DELETE FROM media_files WHERE kind = 'ai_image'")
    op.drop_constraint(op.f("ck_media_files_kind_allowed"), "media_files", type_="check")
    op.create_check_constraint(
        op.f("ck_media_files_kind_allowed"), "media_files", "kind IN ('photo')"
    )
    op.drop_index(op.f("ix_analysis_image_slots_media_file_id"), table_name="analysis_image_slots")
    op.drop_constraint(
        op.f("fk_analysis_image_slots_media_file_id_media_files"),
        "analysis_image_slots",
        type_="foreignkey",
    )
    op.drop_column("analysis_image_slots", "updated_at")
    op.drop_column("analysis_image_slots", "manual_retries")
    op.drop_column("analysis_image_slots", "auto_attempts")
    op.drop_column("analysis_image_slots", "media_file_id")
