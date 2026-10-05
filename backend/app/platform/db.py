"""Database engine, sessions and start-up checks (NFR5.4, NFR5.5).

- One synchronous SQLAlchemy ``Session`` per request (tech-stack Q2), from
  :func:`get_session`. Services commit explicitly; the dependency rolls back on any
  exception and always closes the session.
- No transaction ever spans an outside call such as an email send (NFR5.13).
- At start-up the app checks that the database answers and that Alembic migrations
  are at head, and refuses to start otherwise.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Request
from sqlalchemy import Engine, MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.platform.settings import Settings

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every ORM model (one metadata, one Alembic history)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


SessionFactory = Callable[[], Session]


class DatabaseNotReadyError(RuntimeError):
    """The database is unreachable or its schema is not at the Alembic head."""


def create_db_engine(settings: Settings, **overrides: Any) -> Engine:
    """Create the pooled engine from settings (performance design section 2).

    ``hide_parameters=True`` keeps bound values (emails, hashes) out of database error
    messages, so they can never reach a log (U2 NFR3.2; U1 code-review R-01).
    """
    options: dict[str, Any] = {
        "hide_parameters": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout_seconds,
        "pool_recycle": settings.db_pool_recycle_seconds,
        "pool_pre_ping": True,
    }
    options.update(overrides)
    return create_engine(settings.sqlalchemy_url, **options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Session factory with ``expire_on_commit=False`` (reliability design section 3)."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def check_database(engine: Engine) -> None:
    """Run ``SELECT 1``.

    Raises:
        DatabaseNotReadyError: If the database cannot be reached.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise DatabaseNotReadyError(f"Database is unreachable: {type(exc).__name__}") from exc


def check_migrations_at_head(engine: Engine, script_location: Path = ALEMBIC_DIR) -> None:
    """Compare the database revision with the newest Alembic revision.

    Raises:
        DatabaseNotReadyError: If the schema is behind (or ahead of) the code.
    """
    script = ScriptDirectory(str(script_location))
    expected = set(script.get_heads())
    with engine.connect() as conn:
        current = set(MigrationContext.configure(conn).get_current_heads())
    if current != expected:
        raise DatabaseNotReadyError(
            "Database migrations are not at head "
            f"(database: {sorted(current) or 'empty'}, code: {sorted(expected)}). "
            "Run `uv run alembic upgrade head`."
        )


def ping(session_factory: SessionFactory) -> None:
    """Run ``SELECT 1`` through a short session (used by the readiness probe)."""
    with session_factory() as session:
        session.execute(text("SELECT 1"))


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request, rolled back on error, always closed."""
    factory: SessionFactory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
