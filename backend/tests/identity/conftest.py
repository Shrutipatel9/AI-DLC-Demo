"""API fixtures: the real app, wired to the rolled-back test connection, a frozen clock
and the recording email fake (no network, no paid services)."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, text
from sqlalchemy.orm import Session

from app.identity.models import EmailAttemptCounter, User
from app.main import create_app
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from tests.helpers import make_settings


@pytest.fixture
def email_fake() -> RecordingEmailSender:
    """Recording email fake (tests read codes from it)."""
    return RecordingEmailSender("test")


@pytest.fixture
def settings_overrides() -> dict[str, Any]:
    """Per-test settings overrides (tests may override this fixture)."""
    return {}


@pytest.fixture
def app(
    settings_overrides: dict[str, Any],
    frozen_clock: FrozenClock,
    email_fake: RecordingEmailSender,
    engine: Engine,
    session_factory: Callable[[], Session],
) -> FastAPI:
    """The real API app; the PostgreSQL limiter shares the rolled-back connection."""
    settings = make_settings(RATE_LIMIT_BACKEND="postgres", **settings_overrides)
    return create_app(
        settings,
        clock=frozen_clock,
        email_sender=email_fake,
        engine=engine,
        session_factory=session_factory,
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Test client with the lifespan running."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def bearer(token: str) -> dict[str, str]:
    """Authorization header for an access token."""
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------------- U2 races


class TwoSessions:
    """Independent, really-committing sessions for race tests, with cleanup.

    Users made here are committed so two threads can see them; they (and, by cascade,
    their codes, counters, sessions and reset tokens) are deleted afterwards, together with
    any shadow counters a test registers through :meth:`track_email_hash`.
    """

    def __init__(self, factory: Callable[[], Session]) -> None:
        self.factory = factory
        self._user_ids: list[uuid.UUID] = []
        self._email_hashes: list[str] = []

    def make_user(self, *, verified: bool = True, password_hash: str | None = None) -> uuid.UUID:
        """Insert and commit a user; returns its id."""
        now = datetime.now(UTC)
        with self.factory() as session:
            user = User(
                id=uuid.uuid4(),
                full_name="Race Test",
                email=f"race-{uuid.uuid4().hex[:8]}@example.test",
                password_hash=password_hash or "not-a-real-hash",
                is_verified=verified,
                role="user",
                created_at=now,
                updated_at=now,
                verified_at=now if verified else None,
            )
            session.add(user)
            session.commit()
            self._user_ids.append(user.id)
            return user.id

    def track_email_hash(self, email_hash: str) -> None:
        """Delete this shadow counter at the end of the test."""
        self._email_hashes.append(email_hash)

    def cleanup(self) -> None:
        """Remove everything this fixture created."""
        with self.factory() as session:
            if self._user_ids:
                session.execute(delete(User).where(User.id.in_(self._user_ids)))
            if self._email_hashes:
                session.execute(
                    delete(EmailAttemptCounter).where(
                        EmailAttemptCounter.email_hash.in_(self._email_hashes)
                    )
                )
            session.commit()


@pytest.fixture
def two_sessions(committed_session_factory: Callable[[], Session]) -> Iterator[TwoSessions]:
    """Two (or more) independent committed sessions for race tests; cleans up after itself."""
    races = TwoSessions(committed_session_factory)
    try:
        yield races
    finally:
        races.cleanup()


def run_in_threads(*calls: Callable[[], Any], timeout: float = 10.0) -> list[Any]:
    """Run each call in its own thread and return results (or raised exceptions) in order."""
    results: list[Any] = [None] * len(calls)

    def runner(index: int, call: Callable[[], Any]) -> None:
        try:
            results[index] = call()
        except Exception as exc:  # returned to the test, never swallowed
            results[index] = exc

    threads = [
        threading.Thread(target=runner, args=(index, call), daemon=True)
        for index, call in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout)
        assert not thread.is_alive(), "race test thread did not finish within 10 s"
    return results


def wait_for_lock_waiter(engine: Engine, timeout: float = 10.0) -> None:
    """Block until some PostgreSQL backend is waiting on a row lock (deterministic races)."""
    deadline = time.monotonic() + timeout
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            waiting = conn.execute(
                text("SELECT count(*) FROM pg_locks WHERE NOT granted")
            ).scalar_one()
            if waiting:
                return
            conn.rollback()
            time.sleep(0.01)
    raise AssertionError("no transaction started waiting on a lock")


# --------------------------------------------------------------------- U2 HTTP helpers

FRONTEND = "http://localhost:3000"
CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Origin": FRONTEND}


def post_refresh(client: TestClient, attempt: str | None = None) -> Any:
    """POST /auth/refresh as the web app does (CSRF headers, cookie from the jar)."""
    headers = dict(CSRF_HEADERS)
    if attempt is not None:
        headers["X-Refresh-Attempt"] = attempt
    return client.post("/auth/refresh", headers=headers)


def post_logout(client: TestClient) -> Any:
    """POST /auth/logout as the web app does."""
    return client.post("/auth/logout", headers=CSRF_HEADERS)


def refresh_cookie(client: TestClient) -> str | None:
    """The refresh cookie currently in the client's jar."""
    return client.cookies.get("refresh_token")
