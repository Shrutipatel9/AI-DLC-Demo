"""Alembic environment (NFR1.2, BR8.4).

Database selection, in order:
1. ``sqlalchemy.url`` already set on the config (the test suite does this);
2. ``-x db=test`` -> ``TEST_DATABASE_URL``; ``-x db=e2e`` -> ``E2E_DATABASE_URL``;
3. otherwise ``DATABASE_URL`` from the environment or ``backend/.env``.

The URL never lives in ``alembic.ini``.
"""

from logging.config import fileConfig

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, pool

import app.identity.models
import app.media.models
import app.onboarding.models
import app.payments.models
import app.photos.models
import app.platform.ratelimit_models  # noqa: F401  (registers rate_limit_hits)
from alembic import context
from app.platform.db import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


class _MigrationSettings(BaseSettings):
    """Only the database URLs; migrations need no other configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: SecretStr | None = None
    test_database_url: SecretStr | None = None
    e2e_database_url: SecretStr | None = None


def _resolve_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    choice = context.get_x_argument(as_dictionary=True).get("db", "default")
    settings = _MigrationSettings()
    selected = {
        "default": settings.database_url,
        "test": settings.test_database_url,
        "e2e": settings.e2e_database_url,
    }.get(choice)
    if selected is None:
        raise RuntimeError(
            f"No database URL for -x db={choice}. Set DATABASE_URL, TEST_DATABASE_URL "
            "or E2E_DATABASE_URL (see scripts/ci-env.sh)."
        )
    url = selected.get_secret_value()
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def run_migrations_offline() -> None:
    """Emit SQL without a live connection."""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the selected database."""
    engine = create_engine(_resolve_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
