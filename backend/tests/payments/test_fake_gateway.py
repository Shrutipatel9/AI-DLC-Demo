"""The Stripe fake: recorded sessions, signed events, and HTTP delivery (U5 plan Step 3)."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from app.payments.fake_gateway import FakePaymentGateway, HttpWebhookDeliverer
from app.payments.gateway import COMPLETED, EXPIRED, CheckoutRequest
from tests.payments.conftest import TEST_WEBHOOK_SECRET, RecordedWebhooks


def request(amount: int = 1999) -> CheckoutRequest:
    return CheckoutRequest(
        payment_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        amount=amount,
        currency="USD",
        success_url="http://web.test/payment/success",
        cancel_url="http://web.test/payment/cancel",
        description="report",
    )


@pytest.fixture
def recorder() -> RecordedWebhooks:
    return RecordedWebhooks()


@pytest.fixture
def fake(recorder: RecordedWebhooks) -> FakePaymentGateway:
    return FakePaymentGateway(
        webhook_secret=TEST_WEBHOOK_SECRET, base_url="http://api.test/", deliver=recorder
    )


def test_checkout_records_the_session_and_points_at_the_hosted_test_page(
    fake: FakePaymentGateway,
) -> None:
    sent = request(amount=4500)
    session = fake.create_checkout(sent)
    assert session.session_id.startswith("cs_fake_")
    assert session.url == f"http://api.test/payments/fake-checkout/{session.session_id}"
    recorded = fake.session(session.session_id)
    assert recorded is not None
    assert recorded.request == sent
    assert not recorded.paid
    assert [s.request.amount for s in fake.sessions] == [4500]


def test_pay_delivers_one_signed_completed_event_that_verifies(
    fake: FakePaymentGateway, recorder: RecordedWebhooks
) -> None:
    sent = request()
    session = fake.create_checkout(sent)
    assert fake.pay(session.session_id) == sent.success_url
    assert len(recorder.events) == 1
    body, signature = recorder.events[0]
    event = fake.verify_webhook(body, signature)
    assert event.event_type == COMPLETED
    assert event.is_success
    assert event.session_id == session.session_id
    assert event.payment_id == sent.payment_id
    assert json.loads(body)["data"]["object"]["amount_total"] == sent.amount

    # Paying again redirects but sends nothing more.
    assert fake.pay(session.session_id) == sent.success_url
    assert len(recorder.events) == 1


def test_cancel_returns_the_cancel_url_and_sends_nothing(
    fake: FakePaymentGateway, recorder: RecordedWebhooks
) -> None:
    sent = request()
    session = fake.create_checkout(sent)
    assert fake.cancel(session.session_id) == sent.cancel_url
    assert recorder.events == []
    recorded = fake.session(session.session_id)
    assert recorded is not None
    assert not recorded.paid


def test_unknown_sessions_are_refused(fake: FakePaymentGateway) -> None:
    assert fake.session("cs_fake_" + "0" * 24) is None
    assert fake.pay("cs_fake_" + "0" * 24) is None
    assert fake.cancel("cs_fake_" + "0" * 24) is None
    with pytest.raises(KeyError):
        fake.signed_event("cs_fake_missing", EXPIRED)


def test_events_signed_with_another_secret_do_not_verify(fake: FakePaymentGateway) -> None:
    other = FakePaymentGateway(webhook_secret="whsec_other", base_url="http://api.test")
    session = other.create_checkout(request())
    body, signature = other.signed_event(session.session_id, EXPIRED, payment_status="unpaid")
    with pytest.raises(Exception, match="SIGNATURE_INVALID"):
        fake.verify_webhook(body, signature)
    # The default deliverer of a fake built without one does nothing.
    assert other.pay(session.session_id) == "http://web.test/payment/success"


# --- HTTP delivery ---------------------------------------------------------------------------


class _Receiver(BaseHTTPRequestHandler):
    received: ClassVar[list[tuple[bytes, str | None]]] = []
    statuses: ClassVar[list[int]] = []
    arrived: ClassVar[threading.Event] = threading.Event()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        type(self).received.append((self.rfile.read(length), self.headers.get("Stripe-Signature")))
        status = type(self).statuses.pop(0) if type(self).statuses else 200
        self.send_response(status)
        self.end_headers()
        if status == 200:
            type(self).arrived.set()

    def log_message(self, *_args: object) -> None:
        return


@pytest.fixture
def receiver() -> Iterator[tuple[str, type[_Receiver]]]:
    _Receiver.received = []
    _Receiver.statuses = []
    _Receiver.arrived = threading.Event()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/payments/stripe/webhook", _Receiver
    finally:
        server.shutdown()
        server.server_close()


def test_http_deliverer_posts_the_raw_body_and_signature(
    receiver: tuple[str, type[_Receiver]],
) -> None:
    url, handler = receiver
    HttpWebhookDeliverer(url, delay_seconds=0)(b'{"id":"evt_1"}', "t=1,v1=abc")
    assert handler.arrived.wait(5)
    assert handler.received == [(b'{"id":"evt_1"}', "t=1,v1=abc")]


def test_http_deliverer_retries_a_refused_delivery(receiver: tuple[str, type[_Receiver]]) -> None:
    url, handler = receiver
    handler.statuses = [500]
    HttpWebhookDeliverer(url, delay_seconds=0)(b"{}", "sig")
    assert handler.arrived.wait(5)
    assert len(handler.received) == 2


def test_http_deliverer_needs_an_http_url() -> None:
    with pytest.raises(ValueError, match="http"):
        HttpWebhookDeliverer("file:///etc/passwd", delay_seconds=0)


def test_http_deliverer_logs_when_it_gives_up(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import urllib.error

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("app.payments.fake_gateway.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("app.payments.fake_gateway.urllib.request.urlopen", refuse)
    HttpWebhookDeliverer("http://127.0.0.1:9/hook", delay_seconds=0)._run(b"{}", "sig")
    events = [getattr(record, "event", None) for record in caplog.records]
    assert events.count("payments.fake.delivery_failed") == 3
    assert "payments.fake.delivery_gave_up" in events
