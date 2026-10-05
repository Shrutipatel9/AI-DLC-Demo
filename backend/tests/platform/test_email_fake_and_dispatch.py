"""Email fake, adapter selection, templates and the dispatcher bulkhead.

(BR7.4-BR7.6, NFR12.1, NFR12.2, NFR5.13; AC1.6.1, AC1.6.3, AC1.6.4)
"""

from __future__ import annotations

import threading

import anyio
import anyio.to_thread
import pytest

from app.platform.email import build_email_sender
from app.platform.email.dispatch import EmailDispatcher
from app.platform.email.fake import FakeNotAllowedError, RecordingEmailSender
from app.platform.email.port import EmailPermanentError, EmailTemplate, EmailTimeoutError
from app.platform.email.rendering import render_email
from app.platform.email.smtp import SmtpEmailSender
from app.platform.errors import UpstreamTimeout, UpstreamUnavailable
from app.platform.metrics import Metrics
from app.platform.retry import Deadline
from tests.helpers import make_settings

VARIABLES = {"code": "654321", "expires_minutes": 10, "full_name": "Maya"}


def test_fake_records_codes_for_the_harness() -> None:
    fake = RecordingEmailSender("test")
    fake.send("a@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(5))
    fake.send(
        "a@example.test",
        EmailTemplate.LOGIN_CODE,
        {**VARIABLES, "code": "111111"},
        deadline=Deadline(5),
    )
    assert [m.template for m in fake.sent] == [EmailTemplate.SIGNUP_CODE, EmailTemplate.LOGIN_CODE]
    assert fake.last_code_for("a@example.test") == "111111"
    with pytest.raises(LookupError):
        fake.last_code_for("nobody@example.test")
    fake.clear()
    assert fake.sent == []


@pytest.mark.parametrize("env", ["production", "staging"])
def test_fake_cannot_be_enabled_outside_tests(env: str) -> None:
    with pytest.raises(FakeNotAllowedError):
        RecordingEmailSender(env)


def test_fake_failure_and_deadline_modes() -> None:
    failing = RecordingEmailSender("test", fail_with=EmailPermanentError("rejected"))
    with pytest.raises(EmailPermanentError):
        failing.send("a@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(5))
    slow = RecordingEmailSender("test", delay_seconds=1.0)
    with pytest.raises(EmailTimeoutError):
        slow.send("a@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES, deadline=Deadline(0.05))
    assert slow.sent == []


def test_adapter_is_selected_by_configuration() -> None:
    assert isinstance(build_email_sender(make_settings(EMAIL_BACKEND="fake")), RecordingEmailSender)
    smtp = build_email_sender(make_settings(EMAIL_BACKEND="smtp", SMTP_HOST="127.0.0.1"))
    assert isinstance(smtp, SmtpEmailSender)


@pytest.mark.parametrize("template", list(EmailTemplate))
def test_templates_hold_code_and_expiry_without_images_or_links(template: EmailTemplate) -> None:
    rendered = render_email(template, VARIABLES)
    assert rendered.subject
    for body in (rendered.text, rendered.html):
        assert "654321" in body
        assert "10 minutes" in body
        assert "http" not in body
    assert "<img" not in rendered.html


def test_html_template_escapes_variables() -> None:
    rendered = render_email(EmailTemplate.SIGNUP_CODE, {**VARIABLES, "full_name": "<b>x</b>"})
    assert "<b>x</b>" not in rendered.html
    assert "&lt;b&gt;" in rendered.html


async def _dispatch(dispatcher: EmailDispatcher) -> None:
    dispatcher.start()
    await dispatcher.send("a@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES)


def test_dispatcher_sends_and_maps_failures() -> None:
    metrics = Metrics()
    ok = RecordingEmailSender("test")
    anyio.run(_dispatch, EmailDispatcher(ok, budget_seconds=5, max_concurrency=2, metrics=metrics))
    assert len(ok.sent) == 1

    timeout = RecordingEmailSender("test", fail_with=EmailTimeoutError("slow"))
    with pytest.raises(UpstreamTimeout):
        anyio.run(
            _dispatch,
            EmailDispatcher(timeout, budget_seconds=5, max_concurrency=2, metrics=metrics),
        )

    rejected = RecordingEmailSender("test", fail_with=EmailPermanentError("no"))
    with pytest.raises(UpstreamUnavailable) as caught:
        anyio.run(
            _dispatch,
            EmailDispatcher(rejected, budget_seconds=5, max_concurrency=2, metrics=metrics),
        )
    assert caught.value.status_code == 502
    exposition = metrics.render().decode()
    assert 'email_send_failures_total{reason="timeout"} 1.0' in exposition
    assert 'email_send_failures_total{reason="error"} 1.0' in exposition


def test_dispatcher_requires_start() -> None:
    dispatcher = EmailDispatcher(RecordingEmailSender("test"), budget_seconds=1, max_concurrency=1)

    async def send_without_start() -> None:
        await dispatcher.send("a@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES)

    with pytest.raises(RuntimeError):
        anyio.run(send_without_start)


class BlockingSender:
    """Holds every send until released (ignores the deadline on purpose)."""

    adapter_name = "blocking"

    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Event()

    def send(self, *_args: object, **_kwargs: object) -> None:
        self.started.set()
        self.release.wait(5)


def test_bulkhead_bounds_concurrent_sends_and_times_out_waiters() -> None:
    blocking = BlockingSender()
    dispatcher = EmailDispatcher(blocking, budget_seconds=0.3, max_concurrency=1)
    outcomes: list[str] = []

    async def one() -> None:
        try:
            await dispatcher.send("a@example.test", EmailTemplate.SIGNUP_CODE, VARIABLES)
            outcomes.append("sent")
        except UpstreamUnavailable as exc:
            outcomes.append(f"unavailable-{exc.status_code}")

    async def main() -> None:
        dispatcher.start()
        async with anyio.create_task_group() as group:
            group.start_soon(one)
            await anyio.to_thread.run_sync(blocking.started.wait, 5)
            assert dispatcher.in_flight == 1
            await one()  # waits 0.3 s for the only slot, then gives up with 503
            blocking.release.set()

    anyio.run(main)
    assert outcomes == ["unavailable-503", "sent"]
    assert dispatcher.in_flight == 0
