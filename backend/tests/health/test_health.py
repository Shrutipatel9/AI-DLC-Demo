"""Health probes and fail-fast start-up (NFR5.5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from app.platform.clock import FrozenClock
from app.platform.db import DatabaseNotReadyError
from app.platform.email.fake import RecordingEmailSender
from tests.helpers import make_settings

UNREACHABLE = "postgresql+psycopg://u:p@127.0.0.1:1/none?connect_timeout=1"


def _app(engine: Engine, session_factory: Callable[[], Session], **overrides: str) -> TestClient:
    app = create_app(
        make_settings(**overrides),
        clock=FrozenClock(datetime(2026, 10, 1, tzinfo=UTC)),
        email_sender=RecordingEmailSender("test"),
        engine=engine,
        session_factory=session_factory,
    )
    return TestClient(app, raise_server_exceptions=False)


def test_liveness_is_ok_without_io(engine: Engine, session_factory: Callable[[], Session]) -> None:
    with _app(engine, session_factory) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_checks_the_database(
    engine: Engine, session_factory: Callable[[], Session]
) -> None:
    with _app(engine, session_factory) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_is_503_without_details_when_database_is_down(engine: Engine) -> None:
    broken = sessionmaker(bind=create_engine(UNREACHABLE))
    with _app(engine, broken) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_start_up_fails_fast_when_database_is_unreachable() -> None:
    bad_engine = create_engine(UNREACHABLE)
    app = create_app(make_settings(), email_sender=RecordingEmailSender("test"), engine=bad_engine)
    with pytest.raises(DatabaseNotReadyError), TestClient(app):
        pass
    bad_engine.dispose()


def test_start_up_can_skip_checks_when_configured(session_factory: Callable[[], Session]) -> None:
    bad_engine = create_engine(UNREACHABLE)
    app = create_app(
        make_settings(CHECK_MIGRATIONS_AT_STARTUP="false"),
        email_sender=RecordingEmailSender("test"),
        engine=bad_engine,
        session_factory=session_factory,
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    bad_engine.dispose()
