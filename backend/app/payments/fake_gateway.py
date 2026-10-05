"""The fake payment provider (development and test only; NFR-008, U5 plan Step 3).

It stands in for Stripe so the default test run and the browser journeys never call a paid
service. Settings refuse ``PAYMENT_PROVIDER=fake`` outside development and test.

- :meth:`FakePaymentGateway.create_checkout` records the session (amount, currency, return
  URLs) and returns the URL of a hosted test page served by this API
  (``/payments/fake-checkout/{sessionId}``, see :mod:`app.payments.fake_routes`).
- "Pay" on that page sends the browser to the success URL and delivers a
  ``checkout.session.completed`` event, signed with the webhook secret in Stripe's format, to
  the webhook route. "Cancel" sends the browser to the cancel URL; nothing is charged and no
  event is sent, as with Stripe (AC6.2.3).
- Webhooks are verified by the same code as Stripe's (:func:`verify_and_parse`).

The default deliverer posts the signed event over HTTP to this API's own webhook route after a
short delay (``FAKE_PAYMENT_WEBHOOK_DELAY_SECONDS``), so the browser reaches the "confirming
your payment" screen before the confirmation arrives, as it would with Stripe (AC6.5.1).
Tests inject a recording deliverer instead.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from app.payments.gateway import (
    COMPLETED,
    CheckoutRequest,
    CheckoutSession,
    WebhookEvent,
    sign_payload,
    verify_and_parse,
)

logger = logging.getLogger("payments.fake")

#: ``(raw_body, stripe_signature_header)`` -> delivered (or scheduled).
WebhookDeliverer = Callable[[bytes, str], None]

FAKE_SESSION_PREFIX = "cs_fake_"
FAKE_SESSION_PATTERN = r"^cs_fake_[0-9a-f]{24}$"
WEBHOOK_PATH = "/payments/stripe/webhook"
DELIVERY_TIMEOUT_SECONDS = 10.0
DELIVERY_ATTEMPTS = 3


@dataclass
class FakeSession:
    """A recorded Checkout session."""

    session_id: str
    request: CheckoutRequest
    paid: bool = False


class FakePaymentGateway:
    """Records Checkout sessions and signs webhook events like Stripe.

    Args:
        webhook_secret: The secret the events are signed (and verified) with.
        base_url: This API's public URL (the hosted test page lives under it).
        deliver: Sends a signed event to the webhook; defaults to nothing (tests set one).
    """

    name = "fake"

    def __init__(
        self, *, webhook_secret: str, base_url: str, deliver: WebhookDeliverer | None = None
    ) -> None:
        self._secret = webhook_secret
        self._base_url = base_url.rstrip("/")
        self._deliver: WebhookDeliverer = deliver or (lambda _body, _signature: None)
        self._sessions: dict[str, FakeSession] = {}
        self._lock = threading.Lock()

    # --- The port -----------------------------------------------------------------------------

    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        """Record the session and return the hosted test page's URL."""
        session_id = FAKE_SESSION_PREFIX + secrets.token_hex(12)
        with self._lock:
            self._sessions[session_id] = FakeSession(session_id, request)
        return CheckoutSession(
            session_id=session_id, url=f"{self._base_url}/payments/fake-checkout/{session_id}"
        )

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> WebhookEvent:
        """Verify the signature against the raw body exactly as for Stripe."""
        return verify_and_parse(raw_body, signature, self._secret)

    # --- The hosted test page -----------------------------------------------------------------

    @property
    def sessions(self) -> list[FakeSession]:
        """Every recorded session, oldest first (tests read the recorded amount, AC6.1.3)."""
        with self._lock:
            return list(self._sessions.values())

    def session(self, session_id: str) -> FakeSession | None:
        """The recorded session, or ``None``."""
        with self._lock:
            return self._sessions.get(session_id)

    def pay(self, session_id: str) -> str | None:
        """Mark the session paid, deliver ``checkout.session.completed``; the success URL.

        Paying an already paid session sends nothing more. ``None`` for an unknown session.
        """
        with self._lock:
            recorded = self._sessions.get(session_id)
            if recorded is None:
                return None
            first_payment = not recorded.paid
            recorded.paid = True
        if first_payment:
            body, signature = self.signed_event(session_id, COMPLETED, payment_status="paid")
            self._deliver(body, signature)
            logger.info(
                "fake payment made",
                extra={
                    "event": "payments.fake.paid",
                    "paymentId": str(recorded.request.payment_id),
                },
            )
        return recorded.request.success_url

    def cancel(self, session_id: str) -> str | None:
        """The cancel URL (nothing is charged, no event is sent); ``None`` when unknown."""
        recorded = self.session(session_id)
        return recorded.request.cancel_url if recorded is not None else None

    def signed_event(
        self,
        session_id: str,
        event_type: str,
        *,
        payment_status: str = "paid",
        event_id: str | None = None,
    ) -> tuple[bytes, str]:
        """A Stripe-shaped event about a recorded session and its ``Stripe-Signature``.

        Raises:
            KeyError: For an unknown session.
        """
        recorded = self._sessions[session_id]
        request = recorded.request
        body = json.dumps(
            {
                "id": event_id or "evt_fake_" + secrets.token_hex(12),
                "object": "event",
                "type": event_type,
                "data": {
                    "object": {
                        "id": session_id,
                        "object": "checkout.session",
                        "mode": "payment",
                        "payment_status": payment_status,
                        "amount_total": request.amount,
                        "currency": request.currency.lower(),
                        "client_reference_id": str(request.user_id),
                        "metadata": {
                            "payment_id": str(request.payment_id),
                            "user_id": str(request.user_id),
                        },
                    }
                },
            },
            separators=(",", ":"),
        ).encode()
        return body, sign_payload(body, self._secret, int(time.time()))


class HttpWebhookDeliverer:
    """Posts a signed event to the webhook URL from a background thread, after a delay.

    Retries a refused or failed delivery a few times, like Stripe; a final failure is logged
    (never swallowed silently). Only used with the fake provider (development and test).

    Args:
        url: The webhook URL (``FAKE_PAYMENT_BASE_URL`` + ``/payments/stripe/webhook``).
        delay_seconds: Wait before the first attempt.
    """

    def __init__(self, url: str, delay_seconds: float) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("the webhook URL must be http(s)")
        self.url = url
        self.delay_seconds = delay_seconds

    def __call__(self, raw_body: bytes, signature: str) -> None:
        """Schedule the delivery and return at once."""
        threading.Thread(
            target=self._run, args=(raw_body, signature), name="fake-webhook", daemon=True
        ).start()

    def _post(self, raw_body: bytes, signature: str) -> int:
        request = urllib.request.Request(  # noqa: S310  (http(s) URL checked in __init__)
            self.url,
            data=raw_body,
            method="POST",
            headers={"Content-Type": "application/json", "Stripe-Signature": signature},
        )
        with urllib.request.urlopen(request, timeout=DELIVERY_TIMEOUT_SECONDS) as response:  # noqa: S310  (checked URL)
            return int(response.status)

    def _run(self, raw_body: bytes, signature: str) -> None:
        time.sleep(self.delay_seconds)
        for attempt in range(1, DELIVERY_ATTEMPTS + 1):
            try:
                status = self._post(raw_body, signature)
            except (urllib.error.URLError, OSError) as exc:
                logger.warning(
                    "fake webhook delivery failed",
                    extra={
                        "event": "payments.fake.delivery_failed",
                        "attempt": attempt,
                        "errorClass": type(exc).__name__,
                    },
                )
            else:
                if 200 <= status < 300:
                    return
            time.sleep(1.0)
        logger.error(
            "fake webhook not delivered", extra={"event": "payments.fake.delivery_gave_up"}
        )
