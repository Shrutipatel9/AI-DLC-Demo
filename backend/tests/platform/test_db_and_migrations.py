"""Database checks and the Alembic round-trip (NFR1.2, NFR5.5, BR8.4; AC1.2.2)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.params import Depends
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.platform.db import (
    DatabaseNotReadyError,
    check_database,
    check_migrations_at_head,
    create_db_engine,
    create_session_factory,
    get_session,
    ping,
)
from tests.conftest import alembic_config
from tests.helpers import make_settings

U1_TABLES = {
    "users",
    "one_time_codes",
    "verification_attempts",
    "refresh_sessions",
    "rate_limit_hits",
}


@pytest.fixture
def scratch_database(database_url: str) -> Iterator[str]:
    """A throwaway empty database, dropped afterwards (never the developer's `app`)."""
    name = f"app_migrations_{uuid.uuid4().hex[:8]}_test"
    parsed = make_url(database_url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield parsed.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_migration_upgrade_downgrade_upgrade(scratch_database: str) -> None:
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        with pytest.raises(DatabaseNotReadyError, match="not at head"):
            check_migrations_at_head(engine)
        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= U1_TABLES
        check_migrations_at_head(engine)
        command.downgrade(cfg, "base")
        assert not (U1_TABLES & set(inspect(engine).get_table_names()))
        command.upgrade(cfg, "head")
        check_migrations_at_head(engine)
    finally:
        engine.dispose()


def test_check_database_reports_unreachable_server() -> None:
    engine = create_engine("postgresql+psycopg://u:p@127.0.0.1:1/none?connect_timeout=2")
    with pytest.raises(DatabaseNotReadyError, match="unreachable"):
        check_database(engine)
    engine.dispose()


def test_engine_and_session_factory_from_settings(engine: Engine) -> None:
    settings = make_settings()
    built = create_db_engine(settings)
    try:
        assert built.pool.size() == settings.db_pool_size  # type: ignore[attr-defined]
        check_database(built)
        ping(create_session_factory(built))
    finally:
        built.dispose()
    check_migrations_at_head(engine)


def test_get_session_rolls_back_on_error(engine: Engine) -> None:
    app = FastAPI()
    app.state.session_factory = create_session_factory(engine)
    seen: dict[str, Session] = {}

    @app.get("/fail")
    def fail(request: Request, session: Session = Depends(get_session)) -> None:  # noqa: B008
        session.execute(text("SELECT 1"))
        seen["session"] = session
        raise HTTPException(status_code=409)

    with TestClient(app) as client:
        assert client.get("/fail").status_code == 409
    assert not seen["session"].in_transaction()
