"""Migration 0006: the U6 tables upgrade and downgrade cleanly (NFR-003; U6 plan Step 7)."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from alembic import command
from tests.conftest import alembic_config
from tests.platform.test_db_and_migrations import scratch_database  # noqa: F401  (fixture)

U6_TABLES = {
    "jobs",
    "analysis_runs",
    "analysis_run_photos",
    "analysis_steps",
    "analysis_results",
    "analysis_image_slots",
}


def test_0006_upgrades_and_downgrades_cleanly(scratch_database: str) -> None:  # noqa: F811
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        command.upgrade(cfg, "0006_u6_analysis")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= U6_TABLES
        run_uniques = {
            tuple(u["column_names"]) for u in inspector.get_unique_constraints("analysis_runs")
        }
        assert ("payment_id",) in run_uniques  # one run per payment (AC7.6.3, AC7.1.3)
        job_checks = {c["name"] for c in inspector.get_check_constraints("jobs")}
        assert {"ck_jobs_status_allowed", "ck_jobs_attempts_not_negative"} <= job_checks
        job_indexes = {index["name"] for index in inspector.get_indexes("jobs")}
        assert "ix_jobs_status_created_at" in job_indexes
        photo_fks = {
            fk["referred_table"] for fk in inspector.get_foreign_keys("analysis_run_photos")
        }
        assert photo_fks == {"analysis_runs", "media_files"}

        command.downgrade(cfg, "0005_u5_payments")
        assert not U6_TABLES & set(inspect(engine).get_table_names())
        assert "payments" in set(inspect(engine).get_table_names())
        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= U6_TABLES
    finally:
        engine.dispose()
