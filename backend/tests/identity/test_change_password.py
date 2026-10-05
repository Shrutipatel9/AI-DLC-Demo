"""POST /auth/change-password (WF-U2-8; US11.5; AC11.5.1, AC11.5.3; BR5.1, BR5.3, BR4.5;
NFD post-review R-01, R-09; FD post-review R-03; NFR2.10, NFR5.7)."""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, select

from app.identity.models import RefreshSession
from app.identity.password_change import PasswordChanged, PasswordChangeService
from app.identity.passwords import Argon2Params, PasswordHasher
from app.identity.sessions import Refreshed, SessionPolicy, SessionService
from app.identity.tokens import TokenService
from app.platform.clock import FrozenClock, SystemClock
from app.platform.email.fake import RecordingEmailSender
from tests.factories import SignedInUser, login_code, session_cookie, verified_user
from tests.helpers import make_settings
from tests.identity.conftest import (
    TwoSessions,
    bearer,
    post_refresh,
    run_in_threads,
    wait_for_lock_waiter,
)

NEW_PASSWORD = "Moonrise2027y"


def _change(client: TestClient, token: str, current: str, new: str = NEW_PASSWORD) -> Response:
    return client.post(
        "/auth/change-password",
        json={"currentPassword": current, "newPassword": new},
        headers=bearer(token),
    )


@pytest.fixture
def other_device(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as device:
        yield device


def _sign_in(
    device: TestClient, fake: RecordingEmailSender, user: SignedInUser, clock: FrozenClock
) -> None:
    code = login_code(device, fake, user, clock)
    response = device.post(
        "/auth/verify", json={"email": user.email, "code": code, "purpose": "login"}
    )
    assert response.status_code == 200, response.text


def test_change_keeps_this_session_and_signs_out_other_devices(
    client: TestClient,
    other_device: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
) -> None:
    user = verified_user(client, email_fake)
    _sign_in(other_device, email_fake, user, frozen_clock)
    response = _change(client, user.access_token, user.password)
    assert response.status_code == 204
    assert post_refresh(client).status_code == 200
    kicked = post_refresh(other_device)
    assert kicked.status_code == 401
    assert kicked.json()["error"]["details"] == [{"reason": "REVOKED"}]
    frozen_clock.advance(seconds=61)
    assert (
        client.post("/auth/login", json={"email": user.email, "password": NEW_PASSWORD}).status_code
        == 202
    )


def test_a_wrong_current_password_is_refused_and_changes_nothing(
    client: TestClient,
    other_device: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
) -> None:
    user = verified_user(client, email_fake)
    _sign_in(other_device, email_fake, user, frozen_clock)
    response = _change(client, user.access_token, "Wrong2026pass")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert post_refresh(other_device).status_code == 200
    frozen_clock.advance(seconds=61)
    assert (
        client.post(
            "/auth/login", json={"email": user.email, "password": user.password}
        ).status_code
        == 202
    )


def test_a_weak_new_password_is_a_field_error(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    user = verified_user(client, email_fake)
    response = _change(client, user.access_token, user.password, "password1")
    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert detail == {"field": "newPassword", "reason": "PASSWORD_TOO_WEAK"}


def test_without_a_refresh_cookie_every_session_is_revoked(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    user = verified_user(client, email_fake)
    cookie = client.cookies.get("refresh_token")
    client.cookies.clear()
    assert _change(client, user.access_token, user.password).status_code == 204
    client.cookies.set("refresh_token", cookie or "", path="/auth")
    assert post_refresh(client).json()["error"]["details"] == [{"reason": "REVOKED"}]


def test_another_users_cookie_is_ignored(
    client: TestClient, other_device: TestClient, email_fake: RecordingEmailSender
) -> None:
    alice = verified_user(client, email_fake)
    verified_user(other_device, email_fake)
    bobs_cookie = other_device.cookies.get("refresh_token")
    alices_cookie = client.cookies.get("refresh_token")
    client.cookies.set("refresh_token", bobs_cookie or "", path="/auth")
    assert _change(client, alice.access_token, alice.password).status_code == 204
    assert post_refresh(other_device).status_code == 200  # Bob is untouched
    client.cookies.set("refresh_token", alices_cookie or "", path="/auth")
    assert post_refresh(client).status_code == 401  # Alice's own session was not kept


def test_change_password_needs_an_access_token(client: TestClient) -> None:
    response = client.post(
        "/auth/change-password",
        json={"currentPassword": "Sunrise2026x", "newPassword": NEW_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_a_change_racing_a_refresh_leaves_only_the_kept_family_usable(
    two_sessions: TwoSessions, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = SystemClock()
    settings = make_settings()
    hasher = PasswordHasher(Argon2Params(memory_kib=8, time_cost=1, parallelism=1))
    sessions = SessionService(
        clock=clock, tokens=TokenService.from_settings(settings, clock), policy=SessionPolicy()
    )
    service = PasswordChangeService(clock=clock, hasher=hasher, sessions=sessions)
    user_id = two_sessions.make_user(password_hash=hasher.hash("Sunrise2026x"))
    with two_sessions.factory() as session:
        mine = session_cookie(sessions, session, user_id)
        other = session_cookie(sessions, session, user_id)
    release = threading.Event()
    locked = threading.Event()  # set once the refresh holds its row lock
    real_issue = sessions._tokens.issue_access

    def slow_issue(*args: object, **kwargs: object) -> object:
        locked.set()
        assert release.wait(10)
        return real_issue(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(sessions._tokens, "issue_access", slow_issue)

    def refresh_other() -> object:
        with two_sessions.factory() as session:
            return sessions.refresh(session, other.value, None)

    def change() -> PasswordChanged:
        assert locked.wait(10), "the refresh never took its row lock"
        with two_sessions.factory() as session:
            return asyncio.run(
                service.change(
                    session,
                    user_id=user_id,
                    current_password="Sunrise2026x",
                    new_password=NEW_PASSWORD,
                    cookie_value=mine.value,
                )
            )

    def release_when_change_waits() -> None:
        wait_for_lock_waiter(engine)
        release.set()

    results = run_in_threads(refresh_other, change, release_when_change_waits)
    assert isinstance(results[0], Refreshed), results
    assert isinstance(results[1], PasswordChanged), results
    assert results[1].kept_family == mine.family_id
    with two_sessions.factory() as session:
        rows = session.scalars(
            select(RefreshSession).where(RefreshSession.user_id == user_id)
        ).all()
    usable_families: set[uuid.UUID] = {
        r.family_id for r in rows if r.revoked_at is None and r.rotated_at is None
    }
    assert usable_families == {mine.family_id}
