"""Shared test fixtures.

Prerequisites (see unit-test-instructions.md):
  1. ``docker compose up -d --wait postgres mailpit``
  2. ``source scripts/ci-env.sh`` (sets TEST_DATABASE_URL, throwaway keys, APP_ENV=test)

Integration tests run against a real PostgreSQL database (``app_test``), created and
migrated with Alembic once per test session. Never SQLite (NFR-002, NFR-003).

Isolation: ``db_session`` wraps each test in an outer transaction that is rolled back at
the end; service ``commit()`` calls only release a SAVEPOINT. Concurrency tests that need
real commits use ``committed_session_factory`` and clean up after themselves.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.platform.clock import FrozenClock

BACKEND_DIR = Path(__file__).resolve().parents[1]
FROZEN_START = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is not set. Run `source scripts/ci-env.sh` first "
            "(see unit-test-instructions.md).",
            returncode=4,
        )
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.exit(f"Refusing to run tests against non-test database '{database}'.", returncode=4)
    return url


def _ensure_database(url: str) -> None:
    """Create the test database if it does not exist yet."""
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": parsed.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    finally:
        admin.dispose()


def alembic_config(url: str) -> Config:
    """Alembic configuration pointed at ``url``."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
def database_url() -> str:
    """URL of the migrated test database (created and upgraded to head once)."""
    url = _test_database_url()
    _ensure_database(url)
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """Engine for the test database."""
    eng = create_engine(database_url, pool_size=10, max_overflow=10, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """A connection inside an outer transaction that is always rolled back."""
    conn = engine.connect()
    outer = conn.begin()
    try:
        yield conn
    finally:
        if outer.is_active:
            outer.rollback()
        conn.close()


@pytest.fixture
def session_factory(connection: Connection) -> Callable[[], Session]:
    """Session factory bound to the rolled-back test connection.

    ``commit()`` releases a SAVEPOINT only, so nothing persists past the test.
    """
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture
def db_session(session_factory: Callable[[], Session]) -> Iterator[Session]:
    """One session per test, rolled back at the end."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def committed_session_factory(engine: Engine) -> Callable[[], Session]:
    """Sessions that really commit (for concurrency tests). Tests must clean up."""
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def frozen_clock() -> FrozenClock:
    """A clock frozen at 2026-10-01T10:00:00Z that tests advance explicitly."""
    return FrozenClock(FROZEN_START)


# --- Performance reporting (plan decision D10) ---------------------------------------------

PERF_RESULTS: list[str] = []


def measure_p95(
    name: str,
    target_ms: float,
    run_once: Callable[[], None],
    *,
    prepare: Callable[[], None] | None = None,
    warmup: int = 5,
    samples: int = 50,
) -> float:
    """Measure p95 latency of ``run_once`` (ms); re-run once if the target is exceeded.

    ``prepare`` runs before each call, outside the timed region. Fails only when the
    target is exceeded twice in a row. Results go to the pytest terminal summary.
    """
    import statistics
    import time

    p95 = 0.0
    for attempt in (1, 2):
        for _ in range(warmup):
            if prepare is not None:
                prepare()
            run_once()
        timings: list[float] = []
        for _ in range(samples):
            if prepare is not None:
                prepare()
            started = time.perf_counter()
            run_once()
            timings.append((time.perf_counter() - started) * 1000)
        p95 = statistics.quantiles(timings, n=20)[18]
        PERF_RESULTS.append(
            f"{name}: p95={p95:.1f} ms (target <= {target_ms:.0f} ms, run {attempt})"
        )
        if p95 <= target_ms:
            return p95
    pytest.fail(f"{name} p95 {p95:.1f} ms exceeded {target_ms} ms twice in a row")


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Print the measured p95 values after a perf run."""
    if PERF_RESULTS:
        terminalreporter.section("performance (p95)")
        for line in PERF_RESULTS:
            terminalreporter.write_line(line)
