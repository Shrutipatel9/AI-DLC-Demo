"""Migration 0009 (the chat tables) upgrades and downgrades cleanly."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from alembic import command
from tests.conftest import alembic_config
from tests.platform.test_db_and_migrations import scratch_database  # noqa: F401  (fixture)


def test_0009_upgrades_and_downgrades_cleanly(scratch_database: str) -> None:  # noqa: F811
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        command.upgrade(cfg, "0009_u9_chat")
        inspector = inspect(engine)
        messages = {c["name"] for c in inspector.get_columns("chat_messages")}
        assert {"id", "user_id", "role", "text", "created_at"} <= messages
        assert {c["name"] for c in inspector.get_columns("chat_usage")} == {
            "user_id",
            "day",
            "used",
        }

        command.downgrade(cfg, "0008_u8_report")
        tables = inspect(engine).get_table_names()
        assert "chat_messages" not in tables
        assert "chat_usage" not in tables
        command.upgrade(cfg, "head")
    finally:
        engine.dispose()
