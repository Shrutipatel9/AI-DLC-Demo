"""Latency target for GET /health (NFR9.3). Marker ``perf``."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.main import create_app
from app.platform.email.fake import RecordingEmailSender
from tests.conftest import measure_p95
from tests.helpers import make_settings

pytestmark = pytest.mark.perf


def test_health_p95_within_50ms(engine: Engine, session_factory: Callable[[], Session]) -> None:
    app = create_app(
        make_settings(),
        email_sender=RecordingEmailSender("test"),
        engine=engine,
        session_factory=session_factory,
    )
    with TestClient(app) as client:

        def run_once() -> None:
            assert client.get("/health").status_code == 200

        measure_p95("GET /health", 50, run_once)
