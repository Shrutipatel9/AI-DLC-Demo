"""Migration 0004: the U4 tables upgrade and downgrade cleanly (NFR-003; U4 plan Step 7)."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from alembic import command
from tests.conftest import alembic_config
from tests.platform.test_db_and_migrations import scratch_database  # noqa: F401  (fixture)

U4_TABLES = {"media_files", "photos"}


def test_0004_upgrades_and_downgrades_cleanly(scratch_database: str) -> None:  # noqa: F811
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        command.upgrade(cfg, "0004_u4_photos")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= U4_TABLES
        uniques = {tuple(u["column_names"]) for u in inspector.get_unique_constraints("photos")}
        assert ("user_id", "angle") in uniques  # one current photo per user and angle
        checks = {c["name"] for c in inspector.get_check_constraints("photos")}
        assert "ck_photos_accepted_has_file" in checks

        command.downgrade(cfg, "0003_u3_onboarding")
        assert not U4_TABLES & set(inspect(engine).get_table_names())
        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= U4_TABLES
    finally:
        engine.dispose()
