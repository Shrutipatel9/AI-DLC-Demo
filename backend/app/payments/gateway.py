"""The payment gateway port (contract C10 ``PaymentGateway``) and Stripe webhook parsing.

Two adapters implement the port, chosen by ``PAYMENT_PROVIDER`` (ADR-005):

- :class:`app.payments.stripe_gateway.StripeGateway`: hosted Checkout through the Stripe SDK;
- :class:`app.payments.fake_gateway.FakePaymentGateway`: development/test only; never calls
  Stripe (the default test run uses it, NFR-008).

Both verify webhooks the same way: the ``Stripe-Signature`` header is checked against the RAW
request body with the Stripe SDK's verifier (HMAC-SHA-256, 5-minute timestamp tolerance)
before the body is parsed (AC6.3.3). :func:`sign_payload` produces the same header format,
so the fake's webhooks are verified by exactly the code that verifies Stripe's.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import stripe

#: Stripe's default tolerance for the signature timestamp, in seconds.
SIGNATURE_TOLERANCE_SECONDS = 300

#: Events that mark a payment succeeded (contract C2). ``checkout.session.completed`` only
#: counts when the session's ``payment_status`` is ``paid`` (asynchronous methods complete
#: unpaid first and send ``async_payment_succeeded`` later).
COMPLETED = "checkout.session.completed"
ASYNC_SUCCEEDED = "checkout.session.async_payment_succeeded"
#: Events that mark a pending payment failed (contract C2).
ASYNC_FAILED = "checkout.session.async_payment_failed"
EXPIRED = "checkout.session.expired"
HANDLED_EVENTS = frozenset({COMPLETED, ASYNC_SUCCEEDED, ASYNC_FAILED, EXPIRED})


@dataclass(frozen=True)
class CheckoutRequest:
    """What the service asks the gateway for: one one-time payment at the configured price."""

    payment_id: uuid.UUID
    user_id: uuid.UUID
    amount: int
    currency: str
    success_url: str
    cancel_url: str
    description: str


@dataclass(frozen=True)
class CheckoutSession:
    """A hosted Checkout session: its id and the URL the browser is sent to."""

    session_id: str
    url: str


@dataclass(frozen=True)
class WebhookEvent:
    """The parts of a verified webhook event that the service needs."""

    event_id: str
    event_type: str
    session_id: str | None
    payment_id: uuid.UUID | None
    payment_status: str | None

    @property
    def is_success(self) -> bool:
        """True when the event confirms the money was taken."""
        if self.event_type == ASYNC_SUCCEEDED:
            return True
        return self.event_type == COMPLETED and self.payment_status == "paid"

    @property
    def is_failure(self) -> bool:
        """True when the session expired or an asynchronous payment failed."""
        return self.event_type in (ASYNC_FAILED, EXPIRED)


class WebhookVerificationError(Exception):
    """The webhook is not signed by the provider, or its body cannot be read.

    Args:
        reason: ``SIGNATURE_INVALID`` or ``PAYLOAD_UNREADABLE``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class GatewayError(Exception):
    """The provider could not create the Checkout session (after its retries).

    Args:
        message: A short description for the log (never shown to the user).
        timeout: True when the provider did not answer in time.
    """

    def __init__(self, message: str, *, timeout: bool = False) -> None:
        super().__init__(message)
        self.timeout = timeout


class PaymentGateway(Protocol):
    """The Stripe port (contract C10). Every implementation has a timeout and a test fake."""

    name: str

    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        """Create a hosted Checkout session for one one-time payment.

        Raises:
            GatewayError: When the provider fails or times out.
        """
        ...

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> WebhookEvent:
        """Verify the signature against the raw body, then parse the event.

        Raises:
            WebhookVerificationError: When the signature or the body is not valid.
        """
        ...


def sign_payload(raw_body: bytes, secret: str, timestamp: int) -> str:
    """A ``Stripe-Signature`` header value for ``raw_body`` (Stripe's ``v1`` scheme)."""
    signed = f"{timestamp}.".encode() + raw_body
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_and_parse(
    raw_body: bytes,
    signature: str | None,
    secret: str,
    tolerance: int = SIGNATURE_TOLERANCE_SECONDS,
) -> WebhookEvent:
    """Verify ``signature`` against the raw body with the Stripe SDK, then parse the event.

    Raises:
        WebhookVerificationError: ``SIGNATURE_INVALID`` (missing, wrong or stale signature) or
            ``PAYLOAD_UNREADABLE`` (a signed body that is not a Stripe event).
    """
    try:
        stripe.WebhookSignature.verify_header(raw_body, signature, secret, tolerance)
    except (stripe.SignatureVerificationError, UnicodeDecodeError, ValueError):
        raise WebhookVerificationError("SIGNATURE_INVALID") from None
    return parse_event(raw_body)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _uuid(value: Any) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def parse_event(raw_body: bytes) -> WebhookEvent:
    """Read the event id, type and Checkout session fields from a Stripe event body.

    Raises:
        WebhookVerificationError: ``PAYLOAD_UNREADABLE`` when it is not a Stripe event.
    """
    try:
        data = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise WebhookVerificationError("PAYLOAD_UNREADABLE") from None
    if not isinstance(data, dict):
        raise WebhookVerificationError("PAYLOAD_UNREADABLE")
    event_id, event_type = _text(data.get("id")), _text(data.get("type"))
    if event_id is None or event_type is None or len(event_id) > 255 or len(event_type) > 100:
        raise WebhookVerificationError("PAYLOAD_UNREADABLE")
    payload = data.get("data")
    obj = payload.get("object") if isinstance(payload, dict) else None
    session: dict[str, Any] = obj if isinstance(obj, dict) else {}
    metadata = session.get("metadata")
    return WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        session_id=_text(session.get("id")),
        payment_id=_uuid(metadata.get("payment_id")) if isinstance(metadata, dict) else None,
        payment_status=_text(session.get("payment_status")),
    )
