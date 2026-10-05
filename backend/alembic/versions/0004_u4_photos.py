"""U4 photos: private media files and the current photo per user and angle.

Revision ID: 0004_u4_photos
Revises: 0003_u3_onboarding
Create Date: 2026-10-05 00:00:00+00:00

Creates (US1.10, US5.2, US5.5; DATA-005):
- table ``media_files``: owner (FK users, cascade), kind, content type, the private storage
  key (unique) and size; index on the owner. The bytes live in the FileStorage backend.
- table ``photos``: one row per (user, angle) (unique), status ``accepted`` or ``rejected``,
  the accepted photo's media file (FK, no action; unique), the latest rejection reasons
  (JSONB), the capture method and timestamps. A check keeps ``accepted`` and a file
  together. Angles are free text checked by the service against ``PHOTO_ANGLES``, so
  changing the configured angles needs no migration (ASM-005).

No landmark signature is stored: the same-person check recomputes it every time ([IV] §5).
Downgrade drops both tables in reverse order (stored files are not touched).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_u4_photos"
down_revision: str | Sequence[str] | None = "0003_u3_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the U4 tables."""
    op.create_table(
        "media_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('photo')", name=op.f("ck_media_files_kind_allowed")),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_media_files_size_not_negative")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_media_files_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_files")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_media_files_storage_key")),
    )
    op.create_index(
        op.f("ix_media_files_owner_user_id"), "media_files", ["owner_user_id"], unique=False
    )

    op.create_table(
        "photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("angle", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("media_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("capture_method", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('accepted', 'rejected')", name=op.f("ck_photos_status_allowed")
        ),
        sa.CheckConstraint(
            "capture_method IS NULL OR capture_method IN ('upload', 'camera')",
            name=op.f("ck_photos_capture_method_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'accepted') = (media_file_id IS NOT NULL)",
            name=op.f("ck_photos_accepted_has_file"),
        ),
        sa.ForeignKeyConstraint(
            ["media_file_id"],
            ["media_files.id"],
            name=op.f("fk_photos_media_file_id_media_files"),
            # NO ACTION (checked at statement end), so deleting a user can cascade to both
            # tables; a lone media row still cannot be deleted while a photo uses it.
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_photos_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_photos")),
        sa.UniqueConstraint("media_file_id", name=op.f("uq_photos_media_file_id")),
        sa.UniqueConstraint("user_id", "angle", name=op.f("uq_photos_user_id_angle")),
    )


def downgrade() -> None:
    """Drop the U4 tables in reverse order."""
    op.drop_table("photos")
    op.drop_index(op.f("ix_media_files_owner_user_id"), table_name="media_files")
    op.drop_table("media_files")
