"""Latency targets for the auth endpoints (NFR9.1, NFR9.2). Marker ``perf``.

5 warm-up + 50 measured requests per endpoint through the ASGI app against the test
database, with the real Argon2id parameters and the PostgreSQL limiter. Email uses the
recording fake, so delivery time is excluded (performance design section 1).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from tests.conftest import measure_p95
from tests.factories import VALID_PASSWORD, unique_email, verified_user
from tests.identity.conftest import bearer

pytestmark = pytest.mark.perf


def test_register_p95_within_500ms(client: TestClient, frozen_clock: FrozenClock) -> None:
    def run_once() -> None:
        frozen_clock.advance(seconds=4)  # keeps the per-IP window under its limit
        body = {"fullName": "Perf User", "email": unique_email("perf"), "password": VALID_PASSWORD}
        assert client.post("/auth/register", json=body).status_code == 202

    measure_p95("POST /auth/register", 500, run_once)


def test_login_p95_within_500ms(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)

    def run_once() -> None:
        frozen_clock.advance(seconds=61)  # past the code cooldown
        body = {"email": user.email, "password": VALID_PASSWORD}
        assert client.post("/auth/login", json=body).status_code == 202

    measure_p95("POST /auth/login", 500, run_once)


def test_verify_p95_within_500ms(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    pending: list[str] = []

    def prepare() -> None:
        frozen_clock.advance(seconds=61)
        body = {"email": user.email, "password": VALID_PASSWORD}
        assert client.post("/auth/login", json=body).status_code == 202
        pending.append(email_fake.last_code_for(user.email))

    def run_once() -> None:
        body = {"email": user.email, "code": pending.pop(), "purpose": "login"}
        assert client.post("/auth/verify", json=body).status_code == 200

    measure_p95("POST /auth/verify", 500, run_once, prepare=prepare)


def test_me_p95_within_100ms(client: TestClient, email_fake: RecordingEmailSender) -> None:
    user = verified_user(client, email_fake)
    headers = bearer(user.access_token)

    def run_once() -> None:
        assert client.get("/auth/me", headers=headers).status_code == 200

    measure_p95("GET /auth/me", 100, run_once)
