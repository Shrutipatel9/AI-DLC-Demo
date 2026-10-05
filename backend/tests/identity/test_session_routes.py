"""/auth/refresh, /auth/logout and the reset routes over HTTP, plus cookie attributes
(WF-U2-5, WF-U2-6, WF-U2-7; AC3.5.2-AC3.5.4, AC3.6.1, AC3.6.3, AC3.7.2, AC3.7.3,
AC3.9.2-AC3.9.5; BR2.1-BR2.4, BR2.8, BR3.1, BR4.2-BR4.6; NFR2.5, NFR2.8, NFR2.9)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.platform.email.port import EmailTemplate
from tests.factories import SignedInUser, verified_user
from tests.identity.conftest import bearer, post_logout, post_refresh, refresh_cookie

NEW_PASSWORD = "Moonrise2027y"


def _set_cookie(response: object) -> str:
    return str(response.headers.get("set-cookie", ""))  # type: ignore[attr-defined]


def _reset_token(
    client: TestClient, fake: RecordingEmailSender, user: SignedInUser, clock: FrozenClock
) -> str:
    clock.advance(seconds=61)
    assert client.post("/auth/password/forgot", json={"email": user.email}).status_code == 202
    code = fake.last_code_for(user.email)
    response = client.post("/auth/password/verify-code", json={"email": user.email, "code": code})
    assert response.status_code == 200, response.text
    return str(response.json()["resetToken"])


# ----------------------------------------------------------------------- refresh and logout


def test_refresh_returns_a_new_access_token_and_rotates_the_cookie(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    first_cookie = refresh_cookie(client)
    frozen_clock.advance(minutes=14)
    response = post_refresh(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"accessToken", "expiresAt"}
    assert refresh_cookie(client) not in (None, first_cookie)
    me = client.get("/auth/me", headers=bearer(body["accessToken"]))
    assert me.status_code == 200
    assert me.json()["email"] == user.email


def test_replaying_a_rotated_cookie_is_reuse_and_signs_out_the_family(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    verified_user(client, email_fake)
    stolen = refresh_cookie(client)
    assert post_refresh(client).status_code == 200
    legit = refresh_cookie(client)
    client.cookies.set("refresh_token", stolen or "", path="/auth")
    replay = post_refresh(client)
    assert replay.status_code == 401
    error = replay.json()["error"]
    assert error["code"] == "SESSION_INVALID"
    assert error["details"] == [{"reason": "REUSE_DETECTED"}]
    client.cookies.set("refresh_token", legit or "", path="/auth")
    after = post_refresh(client)
    assert after.json()["error"]["details"] == [{"reason": "REVOKED"}]


def test_expired_and_missing_cookies_are_refused_and_cleared(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    verified_user(client, email_fake)
    frozen_clock.advance(days=7)
    expired = post_refresh(client)
    assert expired.status_code == 401
    assert expired.json()["error"]["details"] == [{"reason": "EXPIRED"}]
    assert "Max-Age=0" in _set_cookie(expired)
    assert refresh_cookie(client) is None
    missing = post_refresh(client)
    assert missing.json()["error"]["details"] == [{"reason": "INVALID"}]


def test_logout_revokes_the_session_and_a_replay_is_revoked(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    verified_user(client, email_fake)
    old_cookie = refresh_cookie(client)
    response = post_logout(client)
    assert response.status_code == 204
    assert response.content == b""
    assert "Max-Age=0" in _set_cookie(response)
    assert refresh_cookie(client) is None
    client.cookies.set("refresh_token", old_cookie or "", path="/auth")
    replay = post_refresh(client)
    assert replay.status_code == 401
    assert replay.json()["error"]["details"] == [{"reason": "REVOKED"}]
    # Logging out again with no cookie still succeeds.
    client.cookies.clear()
    assert post_logout(client).status_code == 204


def test_access_tokens_last_exactly_fifteen_minutes(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    verified_user(client, email_fake)
    token = post_refresh(client).json()["accessToken"]
    frozen_clock.advance(minutes=14, seconds=59)
    assert client.get("/auth/me", headers=bearer(token)).status_code == 200
    frozen_clock.advance(seconds=1)
    denied = client.get("/auth/me", headers=bearer(token))
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "NOT_AUTHENTICATED"


# ----------------------------------------------------------------------- reset routes


def test_forgot_verify_reset_then_old_sessions_are_revoked_and_new_password_works(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    token = _reset_token(client, email_fake, user, frozen_clock)
    assert email_fake.sent[-1].template is EmailTemplate.PASSWORD_RESET_CODE
    # A reset token is never an access token.
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401
    weak = client.post("/auth/password/reset", json={"resetToken": token, "newPassword": "short"})
    assert weak.status_code == 422
    assert weak.json()["error"]["details"][0]["field"] == "newPassword"
    done = client.post(
        "/auth/password/reset", json={"resetToken": token, "newPassword": NEW_PASSWORD}
    )
    assert done.status_code == 204
    again = client.post(
        "/auth/password/reset", json={"resetToken": token, "newPassword": NEW_PASSWORD}
    )
    assert again.status_code == 401
    assert again.json()["error"]["code"] == "RESET_TOKEN_INVALID"
    assert post_refresh(client).json()["error"]["details"] == [{"reason": "REVOKED"}]
    frozen_clock.advance(seconds=61)
    old = client.post("/auth/login", json={"email": user.email, "password": user.password})
    assert old.status_code == 401
    new = client.post("/auth/login", json={"email": user.email, "password": NEW_PASSWORD})
    assert new.status_code == 202


def test_reset_token_expires_after_ten_minutes(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    token = _reset_token(client, email_fake, user, frozen_clock)
    frozen_clock.advance(minutes=10)
    response = client.post(
        "/auth/password/reset", json={"resetToken": token, "newPassword": NEW_PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "RESET_TOKEN_INVALID"


def test_verify_code_errors_use_the_code_contract(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    client.post("/auth/password/forgot", json={"email": user.email})
    bad_shape = client.post("/auth/password/verify-code", json={"email": user.email, "code": "12"})
    assert bad_shape.status_code == 422
    real = email_fake.last_code_for(user.email)
    guess = f"{(int(real) + 1) % 1_000_000:06d}"
    wrong = client.post("/auth/password/verify-code", json={"email": user.email, "code": guess})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["details"] == [{"reason": "CODE_INVALID", "attemptsLeft": 4}]
    frozen_clock.advance(minutes=10)
    expired = client.post("/auth/password/verify-code", json={"email": user.email, "code": real})
    assert expired.json()["error"]["code"] == "CODE_EXPIRED"


# ----------------------------------------------------------------------- cookie attributes


def test_sign_in_sets_an_httponly_seven_day_cookie_on_path_auth(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    user = verified_user(client, email_fake)
    assert user.access_token
    response = post_refresh(client)
    header = _set_cookie(response)
    assert header.startswith("refresh_token=")
    assert "HttpOnly" in header
    assert "Max-Age=604800" in header
    assert "Path=/auth" in header
    assert "SameSite=lax" in header


@pytest.mark.parametrize("settings_overrides", [{"REFRESH_COOKIE_SECURE": "true"}])
def test_secure_flag_comes_from_configuration(
    client: TestClient, email_fake: RecordingEmailSender, settings_overrides: dict[str, str]
) -> None:
    # The test client talks plain http, so it would not send a Secure cookie back; the
    # header on the verify response is what matters here.
    email = verified_user_email_only(client, email_fake)
    code = email_fake.last_code_for(email)
    response = client.post("/auth/verify", json={"email": email, "code": code, "purpose": "signup"})
    assert "Secure" in _set_cookie(response)


def verified_user_email_only(client: TestClient, fake: RecordingEmailSender) -> str:
    from tests.factories import register

    return register(client)


def test_refusals_clear_the_cookie_with_the_same_path(client: TestClient) -> None:
    client.cookies.set("refresh_token", "garbage", path="/auth")
    response = post_refresh(client)
    header = _set_cookie(response)
    assert response.status_code == 401
    assert "Max-Age=0" in header
    assert "Path=/auth" in header
    assert "HttpOnly" in header


def test_the_cookie_lifetime_follows_refresh_token_days(
    app: object, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    from app.main import create_app
    from tests.helpers import make_settings

    settings = make_settings(REFRESH_TOKEN_DAYS="3")
    assert settings.refresh_token_ttl_seconds == 3 * 86_400
    configured = create_app(
        settings,
        clock=frozen_clock,
        email_sender=email_fake,
        engine=app.state.engine,  # type: ignore[attr-defined]
        session_factory=app.state.session_factory,  # type: ignore[attr-defined]
    )
    with TestClient(configured) as client:
        verified_user(client, email_fake)
        header = _set_cookie(post_refresh(client))
        assert "Max-Age=259200" in header
        frozen_clock.advance(timedelta(days=3))
        assert post_refresh(client).json()["error"]["details"] == [{"reason": "EXPIRED"}]


# ----------------------------------------------------------- scalability (NFR11.1, NFR11.4)


def test_two_api_instances_on_one_database_serve_one_family_alternately(
    app: object, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    from app.main import create_app
    from tests.helpers import make_settings

    other = create_app(
        make_settings(RATE_LIMIT_BACKEND="postgres"),
        clock=frozen_clock,
        email_sender=email_fake,
        engine=app.state.engine,  # type: ignore[attr-defined]
        session_factory=app.state.session_factory,  # type: ignore[attr-defined]
    )
    with TestClient(app) as first, TestClient(other) as second:  # type: ignore[arg-type]
        verified_user(first, email_fake)
        value = refresh_cookie(first) or ""
        for turn in range(4):
            target = second if turn % 2 == 0 else first
            target.cookies.clear()
            target.cookies.set("refresh_token", value, path="/auth")
            response = post_refresh(target)
            assert response.status_code == 200, response.text
            value = response.cookies.get("refresh_token") or ""
            assert value


def test_family_and_user_revocations_use_their_indexes(db_session: object) -> None:
    import uuid

    from sqlalchemy import text

    session = db_session
    session.execute(text("SET LOCAL enable_seqscan = off"))  # type: ignore[attr-defined]
    family = (
        session.execute(  # type: ignore[attr-defined]
            text("EXPLAIN SELECT token_id FROM refresh_sessions WHERE family_id = :f"),
            {"f": uuid.uuid4()},
        )
        .scalars()
        .all()
    )
    user = (
        session.execute(  # type: ignore[attr-defined]
            text(
                "EXPLAIN SELECT token_id FROM refresh_sessions WHERE user_id = :u "
                "AND revoked_at IS NULL AND rotated_at IS NULL"
            ),
            {"u": uuid.uuid4()},
        )
        .scalars()
        .all()
    )
    assert "ix_refresh_sessions_family_id" in " ".join(family)
    assert "ix_refresh_sessions_user_id_usable" in " ".join(user)
