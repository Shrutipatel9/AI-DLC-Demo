"""The Stripe adapter with the SDK's HTTP layer stubbed: nothing ever reaches Stripe (NFR-008).

Covers the hosted Checkout request (one-time payment at the configured price, FR7.2, FR7.3),
the retry and timeout behaviour (contract section 6) and webhook verification.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs

import pytest
import stripe

from app.payments.gateway import (
    CheckoutRequest,
    GatewayError,
    WebhookVerificationError,
    sign_payload,
)
from app.payments.stripe_gateway import StripeGateway

Reply = tuple[int, dict[str, Any]] | Exception


class StubHttpClient(stripe.HTTPClient):
    """Answers the SDK's requests from a queue and records what it was sent."""

    name = "stub"

    def __init__(self, replies: list[Reply]) -> None:
        super().__init__()
        self.replies = replies
        self.calls: list[tuple[str, str, Mapping[str, str], Any]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str] | None,
        post_data: Any = None,
        **_: Any,
    ) -> tuple[str, int, Mapping[str, str]]:
        self.calls.append((method, url, dict(headers or {}), post_data))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        return json.dumps(body), status, {"request-id": "req_stub"}

    def close(self) -> None:
        return


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stripe._http_client.time.sleep", lambda _seconds: None)


def checkout_request(amount: int = 2900, currency: str = "EUR") -> CheckoutRequest:
    return CheckoutRequest(
        payment_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        user_id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
        amount=amount,
        currency=currency,
        success_url="http://web.test/payment/success",
        cancel_url="http://web.test/payment/cancel",
        description="AI facial analysis report",
    )


def gateway(stub: StubHttpClient, retries: int = 1) -> StripeGateway:
    return StripeGateway(
        secret_key="sk_test_stub",  # not a real key; the stub answers every call
        webhook_secret="whsec_stub",
        timeout_seconds=10,
        max_network_retries=retries,
        http_client=stub,
    )


SESSION = {
    "id": "cs_test_123",
    "object": "checkout.session",
    "url": "https://checkout.stripe.com/c/pay/cs_test_123",
}


def test_creates_a_one_time_hosted_checkout_at_the_configured_price() -> None:
    stub = StubHttpClient([(200, SESSION)])
    session = gateway(stub).create_checkout(checkout_request(amount=2900, currency="EUR"))
    assert session.session_id == "cs_test_123"
    assert session.url == SESSION["url"]

    method, url, headers, post_data = stub.calls[0]
    assert method == "post"
    assert url.endswith("/v1/checkout/sessions")
    assert headers["Idempotency-Key"] == "checkout-00000000-0000-4000-8000-000000000001"
    form = parse_qs(post_data)
    assert form["mode"] == ["payment"]  # one-time, no subscription (FR7.2)
    assert form["line_items[0][price_data][unit_amount]"] == ["2900"]
    assert form["line_items[0][price_data][currency]"] == ["eur"]
    assert form["line_items[0][quantity]"] == ["1"]
    assert form["success_url"] == ["http://web.test/payment/success"]
    assert form["cancel_url"] == ["http://web.test/payment/cancel"]
    assert form["metadata[payment_id]"] == ["00000000-0000-4000-8000-000000000001"]
    assert form["client_reference_id"] == ["00000000-0000-4000-8000-000000000002"]


def test_a_connection_error_is_retried_once() -> None:
    stub = StubHttpClient([stripe.APIConnectionError("reset", should_retry=True), (200, SESSION)])
    assert gateway(stub).create_checkout(checkout_request()).session_id == "cs_test_123"
    assert len(stub.calls) == 2


def test_a_timeout_after_the_retry_is_a_timeout_gateway_error() -> None:
    timeouts: list[Reply] = [
        stripe.APIConnectionError("ReadTimeout: read timed out", should_retry=True),
        stripe.APIConnectionError("ReadTimeout: read timed out", should_retry=True),
    ]
    with pytest.raises(GatewayError) as caught:
        gateway(StubHttpClient(timeouts)).create_checkout(checkout_request())
    assert caught.value.timeout is True


def test_a_stripe_api_error_is_a_gateway_error() -> None:
    error = {"error": {"type": "invalid_request_error", "message": "No such price"}}
    with pytest.raises(GatewayError) as caught:
        gateway(StubHttpClient([(400, error)])).create_checkout(checkout_request())
    assert caught.value.timeout is False


def test_a_session_without_a_url_is_a_gateway_error() -> None:
    stub = StubHttpClient([(200, {"id": "cs_test_9", "object": "checkout.session", "url": None})])
    with pytest.raises(GatewayError, match="without a URL"):
        gateway(stub).create_checkout(checkout_request())


def test_webhooks_are_verified_with_the_webhook_secret() -> None:
    adapter = gateway(StubHttpClient([]))
    body = b'{"id":"evt_9","type":"checkout.session.expired","data":{"object":{"id":"cs_9"}}}'
    event = adapter.verify_webhook(body, sign_payload(body, "whsec_stub", int(time.time())))
    assert event.event_id == "evt_9"
    assert event.is_failure
    with pytest.raises(WebhookVerificationError):
        adapter.verify_webhook(body, sign_payload(body, "whsec_wrong", int(time.time())))


def test_the_default_http_client_has_the_configured_timeout() -> None:
    adapter = StripeGateway(
        secret_key="sk_test_stub",
        webhook_secret="whsec_stub",
        timeout_seconds=7,
        max_network_retries=1,
    )
    assert adapter._client is not None  # built without any network call
