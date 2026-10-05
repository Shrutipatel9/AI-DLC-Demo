"""Resend, lockout and the login step order (WF-U2-1; US3.3; AC3.3.1-AC3.3.4; BR1.1-BR1.6;
FD post-review R-01, R-06; NFD post-review R-03, R-04, R-11; NFR2.11, NFR2.12, NFR5.6)."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from app.platform.email.port import EmailPermanentError, EmailTemplate
from tests.factories import VALID_PASSWORD, login_code, register, unique_email, verified_user


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def _resend(client: TestClient, email: str, purpose: str) -> Response:
    return client.post("/auth/resend-code", json={"email": email, "purpose": purpose})


def _verify(client: TestClient, email: str, code: str, purpose: str) -> Response:
    return client.post("/auth/verify", json={"email": email, "code": code, "purpose": purpose})


# ------------------------------------------------------------------------- resend (visible)


def test_signup_resend_after_sixty_seconds_replaces_the_old_code(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    email = register(client)
    old = email_fake.last_code_for(email)
    frozen_clock.advance(seconds=60)
    response = _resend(client, email, "signup")
    assert response.status_code == 202
    assert set(response.json()) == {"maskedEmail", "resendAvailableAt", "expiresAt"}
    new = email_fake.last_code_for(email)
    assert len(email_fake.sent) == 2
    if new != old:
        assert _verify(client, email, old, "signup").status_code == 401
    assert _verify(client, email, new, "signup").status_code == 200


def test_signup_resend_within_sixty_seconds_is_refused_with_the_wait(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    email = register(client)
    frozen_clock.advance(seconds=45)
    response = _resend(client, email, "signup")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "CODE_RESEND_COOLDOWN"
    assert response.headers["Retry-After"] == "15"
    assert len(email_fake.sent) == 1


def test_lockout_refuses_codes_and_resends_and_resending_never_resets_the_count(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    email = register(client)
    code = email_fake.last_code_for(email)
    for _ in range(4):
        _verify(client, email, _wrong(code), "signup")
    frozen_clock.advance(seconds=61)
    assert _resend(client, email, "signup").status_code == 202
    fresh = email_fake.last_code_for(email)
    fifth = _verify(client, email, _wrong(fresh), "signup")
    assert fifth.json()["error"]["code"] == "CODE_LOCKED"
    assert fifth.headers["Retry-After"] == "900"
    frozen_clock.advance(seconds=61)
    locked_resend = _resend(client, email, "signup")
    assert locked_resend.status_code == 429
    assert locked_resend.json()["error"]["code"] == "CODE_LOCKED"
    right_but_locked = _verify(client, email, fresh, "signup")
    assert right_but_locked.json()["error"]["code"] == "CODE_LOCKED"


def test_after_the_lockout_the_count_restarts_and_a_new_code_works(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    email = register(client)
    code = email_fake.last_code_for(email)
    for _ in range(5):
        _verify(client, email, _wrong(code), "signup")
    frozen_clock.advance(minutes=14, seconds=59)
    assert _resend(client, email, "signup").status_code == 429
    frozen_clock.advance(seconds=1)
    assert _resend(client, email, "signup").status_code == 202
    fresh = email_fake.last_code_for(email)
    wrong = _verify(client, email, _wrong(fresh), "signup")
    assert wrong.json()["error"]["details"][0]["attemptsLeft"] == 4
    assert _verify(client, email, fresh, "signup").status_code == 200


# ------------------------------------------------------------------- resend (non-revealing)


def test_login_and_reset_resends_answer_identically_and_send_only_when_eligible(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    in_flow = verified_user(client, email_fake)
    login_code(client, email_fake, in_flow, frozen_clock)
    no_flow = verified_user(client, email_fake)
    unverified = register(client)
    frozen_clock.advance(seconds=61)
    sent_before = len(email_fake.sent)
    emails = [in_flow.email, no_flow.email, unverified, unique_email("ghost")]
    bodies = []
    for email in emails:
        response = _resend(client, email, "login")
        assert response.status_code == 202
        body = response.json()
        bodies.append((body["resendAvailableAt"], body["expiresAt"], set(body)))
    assert len({(a, b, frozenset(c)) for a, b, c in bodies}) == 1
    # Only the account whose login password step started a flow gets an email.
    assert [m.to for m in email_fake.sent[sent_before:]] == [in_flow.email]
    assert email_fake.sent[-1].template is EmailTemplate.LOGIN_CODE
    # Cooldown and the 10-minute flow window are silent, too.
    assert _resend(client, in_flow.email, "login").status_code == 202
    frozen_clock.advance(minutes=10)
    assert _resend(client, in_flow.email, "login").status_code == 202
    assert [m.to for m in email_fake.sent[sent_before:]] == [in_flow.email]
    # Reset purpose: unknown and not-requested emails are silent as well.
    for email in (no_flow.email, unique_email("ghost")):
        assert _resend(client, email, "password_reset").status_code == 202
    assert len(email_fake.sent) == sent_before + 1


def test_a_login_resend_supersedes_the_previous_login_code(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    user = verified_user(client, email_fake)
    first = login_code(client, email_fake, user, frozen_clock)
    frozen_clock.advance(seconds=61)
    assert _resend(client, user.email, "login").status_code == 202
    second = email_fake.last_code_for(user.email)
    if second != first:
        assert _verify(client, user.email, first, "login").status_code == 401
    assert _verify(client, user.email, second, "login").status_code == 200


def test_a_failed_background_send_still_answers_202_and_is_logged_at_error(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = verified_user(client, email_fake)
    frozen_clock.advance(seconds=61)
    email_fake.fail_with = EmailPermanentError("mailbox unavailable")
    caplog.set_level(logging.ERROR)
    response = client.post("/auth/password/forgot", json={"email": user.email})
    assert response.status_code == 202
    errors = [r for r in caplog.records if getattr(r, "event", None) == "vendor.failed"]
    assert errors
    assert errors[0].levelno == logging.ERROR
    # The cooldown still holds after a failed send; after it, the user can try again.
    email_fake.fail_with = None
    assert _resend(client, user.email, "password_reset").status_code == 202
    assert not [m for m in email_fake.sent if m.template is EmailTemplate.PASSWORD_RESET_CODE]
    frozen_clock.advance(seconds=60)
    assert _resend(client, user.email, "password_reset").status_code == 202
    assert email_fake.sent[-1].template is EmailTemplate.PASSWORD_RESET_CODE


def test_login_verify_for_an_unknown_email_counts_down_and_locks_like_a_real_account(
    client: TestClient,
) -> None:
    email = unique_email("ghost")
    lefts = [_verify(client, email, "123456", "login").json()["error"]["details"] for _ in range(4)]
    assert [d[0]["attemptsLeft"] for d in lefts] == [4, 3, 2, 1]
    fifth = _verify(client, email, "123456", "login")
    assert fifth.status_code == 429
    assert fifth.json()["error"]["code"] == "CODE_LOCKED"
    assert fifth.headers["Retry-After"] == "900"


# ------------------------------------------------------------- login step order (R-04)


def _lock_login(
    client: TestClient, fake: RecordingEmailSender, clock: FrozenClock
) -> tuple[str, str]:
    user = verified_user(client, fake)
    code = login_code(client, fake, user, clock)
    for _ in range(5):
        _verify(client, user.email, _wrong(code), "login")
    clock.advance(seconds=61)
    return user.email, user.password


def test_locked_login_with_the_right_password_is_code_locked(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    email, password = _lock_login(client, email_fake, frozen_clock)
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "CODE_LOCKED"
    assert int(response.headers["Retry-After"]) == 900 - 61


def test_locked_login_with_a_wrong_password_is_just_invalid_credentials(
    client: TestClient, email_fake: RecordingEmailSender, frozen_clock: FrozenClock
) -> None:
    email, _ = _lock_login(client, email_fake, frozen_clock)
    response = client.post("/auth/login", json={"email": email, "password": "Wrong2026pass"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_for_an_unknown_email_is_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"email": unique_email("ghost"), "password": VALID_PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


# ------------------------------------------------------------- background delivery branches


class _Decision:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.retry_after = 0
        self.count = 0


class _Limiter:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    def check_and_record(self, key: str, limit: int, window_seconds: int) -> _Decision:
        return _Decision(self.allowed)


def _delivery(
    session_factory: object,
    clock: FrozenClock,
    fake: RecordingEmailSender,
    *,
    allowed: bool = True,
) -> tuple[object, object]:
    from app.identity.codes import CodeService
    from app.identity.delivery import CodeDelivery
    from app.platform.email.dispatch import EmailDispatcher
    from app.platform.metrics import Metrics
    from tests.helpers import make_settings

    codes = CodeService(hmac_key=make_settings().code_key(), clock=clock)
    dispatcher = EmailDispatcher(fake, budget_seconds=5, max_concurrency=2)
    delivery = CodeDelivery(
        session_factory=session_factory,  # type: ignore[arg-type]
        codes=codes,
        dispatcher=dispatcher,
        limiter=_Limiter(allowed),
        metrics=Metrics(),
        email_hourly_cap=10,
    )
    return delivery, dispatcher


def _pending_for(client: TestClient, fake: RecordingEmailSender) -> object:
    import uuid

    from app.identity.delivery import PendingCode
    from app.identity.models import CodePurpose

    user = verified_user(client, fake)
    return PendingCode(
        uuid.UUID(user.user_id), user.email, user.full_name, CodePurpose.PASSWORD_RESET
    )


def _run(delivery: object, dispatcher: object, pending: object) -> None:
    import asyncio

    async def go() -> None:
        dispatcher.start()  # type: ignore[attr-defined]
        await delivery.deliver(pending)  # type: ignore[attr-defined]

    asyncio.run(go())


def test_background_delivery_skips_a_locked_account_without_sending(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    session_factory: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.identity.models import VerificationAttemptCounter

    pending = _pending_for(client, email_fake)
    with session_factory() as session:  # type: ignore[operator]
        session.merge(
            VerificationAttemptCounter(
                user_id=pending.user_id,  # type: ignore[attr-defined]
                purpose="password_reset",
                failed_count=5,
                locked_until=frozen_clock.now() + timedelta(minutes=15),
            )
        )
        session.commit()
    sent = len(email_fake.sent)
    caplog.set_level(logging.INFO)
    delivery, dispatcher = _delivery(session_factory, frozen_clock, email_fake)
    _run(delivery, dispatcher, pending)
    assert len(email_fake.sent) == sent
    assert [r for r in caplog.records if getattr(r, "event", None) == "auth.code.not_sent"]


def test_background_delivery_logs_an_unexpected_issue_failure(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pending = _pending_for(client, email_fake)

    def broken_factory() -> object:
        raise RuntimeError("no database")

    caplog.set_level(logging.ERROR)
    delivery, dispatcher = _delivery(broken_factory, frozen_clock, email_fake)
    _run(delivery, dispatcher, pending)
    errors = [r for r in caplog.records if getattr(r, "event", None) == "auth.code.issue_failed"]
    assert errors
    assert errors[0].levelno == logging.ERROR


def test_background_delivery_respects_the_hourly_email_cap(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    session_factory: object,
) -> None:
    from sqlalchemy import select

    from app.identity.models import OneTimeCode

    pending = _pending_for(client, email_fake)
    sent = len(email_fake.sent)
    delivery, dispatcher = _delivery(session_factory, frozen_clock, email_fake, allowed=False)
    _run(delivery, dispatcher, pending)
    assert len(email_fake.sent) == sent
    with session_factory() as session:  # type: ignore[operator]
        codes = session.scalars(
            select(OneTimeCode).where(
                OneTimeCode.user_id == pending.user_id,  # type: ignore[attr-defined]
                OneTimeCode.purpose == "password_reset",
            )
        ).all()
    assert codes
    assert all(code.superseded_at is not None for code in codes)


def test_a_failed_supersede_is_logged_not_raised(
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    session_factory: object,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = _pending_for(client, email_fake)
    delivery, dispatcher = _delivery(session_factory, frozen_clock, email_fake)
    email_fake.fail_with = EmailPermanentError("rejected")

    def broken_supersede(*_args: object) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(delivery._codes, "supersede", broken_supersede)  # type: ignore[attr-defined]
    caplog.set_level(logging.ERROR)
    _run(delivery, dispatcher, pending)
    events = {getattr(r, "event", None) for r in caplog.records}
    assert {"vendor.failed", "auth.code.supersede_failed"} <= events


def test_change_password_for_a_deleted_user_is_not_authenticated(
    client: TestClient, email_fake: RecordingEmailSender, db_session: object
) -> None:
    import uuid

    from sqlalchemy import delete

    from app.identity.models import User
    from tests.identity.conftest import bearer

    user = verified_user(client, email_fake)
    db_session.execute(delete(User).where(User.id == uuid.UUID(user.user_id)))  # type: ignore[attr-defined]
    db_session.commit()  # type: ignore[attr-defined]
    response = client.post(
        "/auth/change-password",
        json={"currentPassword": user.password, "newPassword": "Moonrise2027y"},
        headers=bearer(user.access_token),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


# ------------------------------------------------------------ per-IP throttle (NFR2.13)


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/auth/resend-code", {"email": "a@example.test", "purpose": "login"}),
        ("/auth/password/forgot", {"email": "a@example.test"}),
        ("/auth/password/verify-code", {"email": "a@example.test", "code": "123456"}),
        ("/auth/password/reset", {"resetToken": "x" * 43, "newPassword": "Moonrise2027y"}),
    ],
)
def test_the_21st_call_in_a_minute_is_rate_limited(
    client: TestClient, path: str, body: dict[str, str]
) -> None:
    codes = [client.post(path, json=body).json().get("error", {}).get("code") for _ in range(21)]
    # verify-code may answer CODE_LOCKED first (the shadow lockout); that is not the limiter.
    assert "RATE_LIMITED" not in codes[:20]
    assert codes[20] == "RATE_LIMITED"


def test_change_password_is_rate_limited_per_ip(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    from tests.identity.conftest import bearer

    user = verified_user(client, email_fake)
    body = {"currentPassword": "Wrong2026pass", "newPassword": "Moonrise2027y"}
    statuses = [
        client.post(
            "/auth/change-password", json=body, headers=bearer(user.access_token)
        ).status_code
        for _ in range(21)
    ]
    assert statuses[:20] == [401] * 20
    assert statuses[20] == 429


def test_refresh_and_logout_have_their_own_higher_limit(client: TestClient) -> None:
    from tests.identity.conftest import CSRF_HEADERS

    for path in ("/auth/refresh", "/auth/logout"):
        statuses = [client.post(path, headers=CSRF_HEADERS).status_code for _ in range(61)]
        assert 429 not in statuses[:60]
        assert statuses[60] == 429
        assert client.post(path, headers=CSRF_HEADERS).json()["error"]["code"] == "RATE_LIMITED"
