"""Ownership helper (BR6.2, NFR3.4; AC1.8.1), per-IP throttle (NFR2.9) and the log
canary (BR6.3, NFR3.2; AC1.8.3)."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.identity.public import AuthenticatedUser, require_owner, require_role
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.platform.errors import NotFound, install_exception_handlers
from app.platform.logging import JsonFormatter
from tests.factories import VALID_PASSWORD, register, unique_email
from tests.identity.conftest import bearer

ALICE = AuthenticatedUser(user_id=uuid.uuid4(), role="user")


# ----------------------------------------------------------------------- ownership (3)


def test_owner_may_access_their_record() -> None:
    require_owner(ALICE.user_id, ALICE)


def test_other_users_record_is_404() -> None:
    with pytest.raises(NotFound) as caught:
        require_owner(uuid.uuid4(), ALICE)
    assert caught.value.status_code == 404


def test_role_dependency_reads_the_token_role() -> None:
    app = FastAPI()
    install_exception_handlers(app)
    check = require_role("admin")

    @app.get("/admin-only")
    def admin_only(user: AuthenticatedUser = Depends(check)) -> dict[str, str]:  # noqa: B008
        return {"role": user.role}

    from app.identity.dependencies import current_user

    app.dependency_overrides[current_user] = lambda: ALICE
    with TestClient(app) as client:
        response = client.get("/admin-only")
    assert response.status_code == 404
    assert check(AuthenticatedUser(ALICE.user_id, "admin")).role == "admin"


# ----------------------------------------------------------------------- per-IP throttle (4)


def _register_body() -> dict[str, str]:
    return {"fullName": "Maya", "email": unique_email(), "password": VALID_PASSWORD}


def test_twenty_first_register_from_one_ip_is_rate_limited(client: TestClient) -> None:
    statuses = [client.post("/auth/register", json=_register_body()).status_code for _ in range(21)]
    assert statuses[:20] == [202] * 20
    assert statuses[20] == 429


def test_rate_limited_response_shape(client: TestClient, frozen_clock: FrozenClock) -> None:
    for _ in range(20):
        client.post(
            "/auth/verify", json={"email": unique_email(), "code": "123456", "purpose": "login"}
        )
    response = client.post(
        "/auth/verify", json={"email": unique_email(), "code": "123456", "purpose": "login"}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert response.headers["Retry-After"] == "60"
    frozen_clock.advance(seconds=61)
    after = client.post(
        "/auth/verify", json={"email": unique_email(), "code": "123456", "purpose": "login"}
    )
    assert after.status_code == 401


def test_limits_are_per_route_and_per_ip(client: TestClient, app: FastAPI) -> None:
    for _ in range(20):
        client.post("/auth/login", json={"email": unique_email(), "password": "Wrong2026x"})
    assert (
        client.post("/auth/login", json={"email": unique_email(), "password": "x"}).status_code
        == 429
    )
    # Another route from the same IP is unaffected.
    assert client.post("/auth/register", json=_register_body()).status_code == 202
    # Another IP is unaffected.
    with TestClient(app, client=("203.0.113.50", 40000)) as other:
        response = other.post(
            "/auth/login", json={"email": unique_email(), "password": "Wrong2026x"}
        )
        assert response.status_code == 401


def test_rate_limited_requests_are_logged_and_counted(
    client: TestClient, app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    for _ in range(21):
        client.post("/auth/login", json={"email": unique_email(), "password": "Wrong2026x"})
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "auth.rate_limited" in events
    assert 'rate_limited_total{route="/auth/login"} 1.0' in app.state.metrics.render().decode()


# ----------------------------------------------------------------------- log canary (1)


def test_logs_never_contain_passwords_codes_tokens_or_full_emails(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    canary_password = "Canary2026Secret"
    email = register(client, password=canary_password)
    signup_code = email_fake.last_code_for(email)
    wrong = client.post(
        "/auth/verify", json={"email": email, "code": "000000", "purpose": "signup"}
    )
    assert wrong.status_code == 401
    verified = client.post(
        "/auth/verify", json={"email": email, "code": signup_code, "purpose": "signup"}
    )
    access = verified.json()["accessToken"]
    cookie = verified.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    client.post("/auth/login", json={"email": email, "password": "WrongCanary2026"})
    frozen_clock.advance(seconds=61)
    client.post("/auth/login", json={"email": email, "password": canary_password})
    login = email_fake.last_code_for(email)
    client.post("/auth/verify", json={"email": email, "code": login, "purpose": "login"})
    client.get("/auth/me", headers=bearer(access))

    formatter = JsonFormatter()
    output = "\n".join(formatter.format(record) for record in caplog.records)
    events = {getattr(r, "event", None) for r in caplog.records}
    assert {
        "auth.signup.requested",
        "auth.code.sent",
        "auth.code.failed",
        "auth.verified",
        "auth.login.failed",
        "auth.login.code_sent",
        "http.request",
    } <= events
    for secret in (canary_password, "WrongCanary2026", signup_code, login, access, cookie, email):
        assert secret not in output
    assert "•••@example.test" in output
