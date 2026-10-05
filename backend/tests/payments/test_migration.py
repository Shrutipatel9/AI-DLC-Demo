"""Migration 0005: the U5 tables upgrade and downgrade cleanly (NFR-003; U5 plan Step 4)."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from alembic import command
from tests.conftest import alembic_config
from tests.platform.test_db_and_migrations import scratch_database  # noqa: F401  (fixture)

U5_TABLES = {"payments", "payment_events"}


def test_0005_upgrades_and_downgrades_cleanly(scratch_database: str) -> None:  # noqa: F811
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        command.upgrade(cfg, "0005_u5_payments")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= U5_TABLES
        event_uniques = {
            tuple(u["column_names"]) for u in inspector.get_unique_constraints("payment_events")
        }
        assert ("provider_event_id",) in event_uniques  # idempotency by event id (AC6.3.2)
        payment_uniques = {
            tuple(u["column_names"]) for u in inspector.get_unique_constraints("payments")
        }
        assert ("provider_session_id",) in payment_uniques
        checks = {c["name"] for c in inspector.get_check_constraints("payments")}
        assert {"ck_payments_status_allowed", "ck_payments_paid_at_set"} <= checks

        command.downgrade(cfg, "0004_u4_photos")
        assert not U5_TABLES & set(inspect(engine).get_table_names())
        assert "photos" in set(inspect(engine).get_table_names())
        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= U5_TABLES
    finally:
        engine.dispose()
