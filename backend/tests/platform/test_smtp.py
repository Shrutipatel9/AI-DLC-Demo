"""SMTP adapter against a local stub server (NFR5.1-NFR5.3, NFR12.1; AC1.6.2)."""

from __future__ import annotations

import asyncio
import smtplib
import time
from collections.abc import Iterator
from email import message_from_bytes
from email.message import Message
from typing import Any

import pytest
from aiosmtpd.controller import Controller

from app.platform.email.port import (
    EmailPermanentError,
    EmailTemplate,
    EmailTimeoutError,
    EmailTransientError,
)
from app.platform.email.smtp import SmtpConfig, SmtpEmailSender, classify_smtp_error
from app.platform.retry import Deadline, RetryPolicy
from tests.helpers import free_port


class StubHandler:
    """aiosmtpd handler that can fail or stall on command."""

    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.data_replies: list[str] = []
        self.stall_seconds = 0.0

    async def handle_DATA(self, _server: Any, _session: Any, envelope: Any) -> str:  # noqa: N802
        if self.stall_seconds:
            await asyncio.sleep(self.stall_seconds)
        if self.data_replies:
            return self.data_replies.pop(0)
        self.messages.append(message_from_bytes(envelope.content))
        return "250 Message accepted"


@pytest.fixture
def smtp_stub() -> Iterator[tuple[StubHandler, int]]:
    handler = StubHandler()
    port = free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield handler, port
    finally:
        controller.stop()


def _sender(port: int, **policy: Any) -> SmtpEmailSender:
    config = SmtpConfig(host="127.0.0.1", port=port, sender="no-reply@example.test")
    defaults: dict[str, Any] = {"sleep": lambda _s: None, "jitter": lambda _a, _b: 0.0}
    defaults.update(policy)
    return SmtpEmailSender(config, RetryPolicy(**defaults))


VARIABLES = {"code": "123456", "expires_minutes": 10, "full_name": "Maya"}


def test_send_delivers_text_and_html_with_code(smtp_stub: tuple[StubHandler, int]) -> None:
    handler, port = smtp_stub
    _sender(port).send(
        "maya@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(25)
    )
    assert len(handler.messages) == 1
    message = handler.messages[0]
    assert message["To"] == "maya@example.test"
    assert message["Subject"] == "Your FaceIQ sign-up code"
    parts = {part.get_content_type(): part.get_payload(decode=True) for part in message.walk()}
    assert b"123456" in parts["text/plain"]
    assert b"123456" in parts["text/html"]


def test_permanent_rejection_is_not_retried(smtp_stub: tuple[StubHandler, int]) -> None:
    handler, port = smtp_stub
    handler.data_replies = ["550 Mailbox unavailable", "250 OK"]
    with pytest.raises(EmailPermanentError):
        _sender(port).send(
            "x@example.test", EmailTemplate.LOGIN_CODE, VARIABLES, deadline=Deadline(25)
        )
    assert handler.data_replies == ["250 OK"]  # only one attempt was made


def test_transient_rejection_is_retried_then_succeeds(smtp_stub: tuple[StubHandler, int]) -> None:
    handler, port = smtp_stub
    handler.data_replies = ["451 Try again later"]
    _sender(port).send("x@example.test", EmailTemplate.LOGIN_CODE, VARIABLES, deadline=Deadline(25))
    assert len(handler.messages) == 1


def test_stall_after_data_returns_by_the_budget(smtp_stub: tuple[StubHandler, int]) -> None:
    handler, port = smtp_stub
    handler.stall_seconds = 30
    budget = 3.0
    sender = _sender(port, attempt_timeout=1.0, min_attempt_seconds=0.2)
    started = time.monotonic()
    with pytest.raises(EmailTimeoutError):
        sender.send(
            "x@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(budget)
        )
    assert time.monotonic() - started <= budget + 1.0


def test_watchdog_cuts_a_single_stalled_attempt_at_the_deadline(
    smtp_stub: tuple[StubHandler, int],
) -> None:
    handler, port = smtp_stub
    handler.stall_seconds = 30
    # Socket timeout (10 s) is longer than the budget, so only the watchdog/budget stops it.
    sender = _sender(port, attempt_timeout=10.0, min_attempt_seconds=0.2, max_attempts=1)
    started = time.monotonic()
    with pytest.raises(EmailTimeoutError):
        sender.send("x@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(2.5))
    assert time.monotonic() - started <= 3.5


def test_connection_refused_is_a_transient_failure() -> None:
    sender = _sender(free_port(), max_attempts=2)
    with pytest.raises(EmailTransientError):
        sender.send("x@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(10))


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (smtplib.SMTPResponseException(421, b"busy"), EmailTransientError),
        (smtplib.SMTPResponseException(553, b"bad"), EmailPermanentError),
        (smtplib.SMTPRecipientsRefused({"a": (550, b"no")}), EmailPermanentError),
        (smtplib.SMTPRecipientsRefused({"a": (450, b"later")}), EmailTransientError),
        (TimeoutError(), EmailTimeoutError),
        (ConnectionResetError(), EmailTransientError),
    ],
)
def test_classify_smtp_error(exc: BaseException, expected: type[Exception]) -> None:
    assert classify_smtp_error(exc) is expected


def test_starttls_verifies_the_configured_host(
    smtp_stub: tuple[StubHandler, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: connect() after a bare SMTP() left _host empty, so starttls() failed
    # with "check_hostname requires server_hostname" and no code email was sent.
    handler, port = smtp_stub
    seen: list[str] = []

    def fake_starttls(self: smtplib.SMTP, **_kwargs: Any) -> tuple[int, bytes]:
        seen.append(self._host)  # type: ignore[attr-defined]
        return 220, b"ready"

    monkeypatch.setattr(smtplib.SMTP, "starttls", fake_starttls)
    config = SmtpConfig(host="127.0.0.1", port=port, sender="no-reply@example.test", starttls=True)
    SmtpEmailSender(config).send(
        "maya@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(25)
    )
    assert seen == ["127.0.0.1"]
    assert len(handler.messages) == 1
