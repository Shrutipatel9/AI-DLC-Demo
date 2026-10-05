"""U2 endpoint latency targets (NFR9.1-NFR9.5). Marker ``perf``.

5 warm-up + 50 measured requests per endpoint through the ASGI app against the test
database, with the real Argon2id parameters and the PostgreSQL limiter (the limits are
raised so the limiter still runs but never refuses). One automatic re-run per target.
Email uses the recording fake, so delivery time is excluded (performance requirements).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from tests.conftest import measure_p95
from tests.factories import unique_email, verified_user
from tests.identity.conftest import CSRF_HEADERS, bearer, post_logout, post_refresh

pytestmark = pytest.mark.perf

PASSWORDS = ("Sunrise2026x", "Moonrise2027y")


@pytest.fixture
def settings_overrides() -> dict[str, Any]:
    return {"AUTH_RATE_LIMIT_PER_MINUTE": 100_000, "REFRESH_RATE_LIMIT_PER_MINUTE": 100_000}


def test_refresh_p95_within_200ms(client: TestClient, email_fake: RecordingEmailSender) -> None:
    verified_user(client, email_fake)

    def run_once() -> None:
        assert post_refresh(client).status_code == 200

    measure_p95("POST /auth/refresh", 200, run_once)


def test_logout_p95_within_200ms(
    app: FastAPI, client: TestClient, email_fake: RecordingEmailSender
) -> None:
    user = verified_user(client, email_fake)
    identity = app.state.identity

    def prepare() -> None:
        import uuid

        with app.state.session_factory() as session:
            token = identity.sessions.start(session, uuid.UUID(user.user_id))
            session.commit()
        client.cookies.set("refresh_token", token.value, path="/auth")

    def run_once() -> None:
        assert post_logout(client).status_code == 204

    measure_p95("POST /auth/logout", 200, run_once, prepare=prepare)


def test_resend_p95_within_200ms(client: TestClient, frozen_clock: FrozenClock) -> None:
    def run_once() -> None:
        body = {"email": unique_email("perf"), "purpose": "login"}
        assert client.post("/auth/resend-code", json=body).status_code == 202

    measure_p95("POST /auth/resend-code", 200, run_once)


def test_forgot_and_verify_code_p95_within_500ms(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)

    def forgot() -> None:
        frozen_clock.advance(seconds=61)
        assert client.post("/auth/password/forgot", json={"email": user.email}).status_code == 202

    measure_p95("POST /auth/password/forgot", 500, forgot)

    def prepare() -> None:
        forgot()

    def verify() -> None:
        code = email_fake.last_code_for(user.email)
        body = {"email": user.email, "code": code}
        assert client.post("/auth/password/verify-code", json=body).status_code == 200

    measure_p95("POST /auth/password/verify-code", 500, verify, prepare=prepare)


def test_reset_and_change_password_p95_within_500ms(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    tokens: list[str] = []
    state = {"current": 0}

    def prepare_reset() -> None:
        frozen_clock.advance(seconds=61)
        client.post("/auth/password/forgot", json={"email": user.email})
        code = email_fake.last_code_for(user.email)
        response = client.post(
            "/auth/password/verify-code", json={"email": user.email, "code": code}
        )
        tokens.append(response.json()["resetToken"])

    def reset() -> None:
        state["current"] = 1 - state["current"]
        body = {"resetToken": tokens.pop(), "newPassword": PASSWORDS[state["current"]]}
        assert client.post("/auth/password/reset", json=body).status_code == 204

    measure_p95("POST /auth/password/reset", 500, reset, prepare=prepare_reset)

    access = {"token": ""}

    def prepare_change() -> None:
        frozen_clock.advance(seconds=61)
        client.post(
            "/auth/login", json={"email": user.email, "password": PASSWORDS[state["current"]]}
        )
        code = email_fake.last_code_for(user.email)
        response = client.post(
            "/auth/verify", json={"email": user.email, "code": code, "purpose": "login"}
        )
        access["token"] = response.json()["accessToken"]

    def change() -> None:
        current = PASSWORDS[state["current"]]
        state["current"] = 1 - state["current"]
        body = {"currentPassword": current, "newPassword": PASSWORDS[state["current"]]}
        response = client.post(
            "/auth/change-password",
            json=body,
            headers={**bearer(access["token"]), **CSRF_HEADERS},
        )
        assert response.status_code == 204, response.text

    measure_p95("POST /auth/change-password", 500, change, prepare=prepare_change)
