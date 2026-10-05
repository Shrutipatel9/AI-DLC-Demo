"""Stripe adapter for the payment gateway port (FR7.2; contract C10, section 6).

Creates a hosted Checkout session in ``payment`` mode (one-time payment, no subscription) for
the configured price, with inline ``price_data`` so a price change in configuration needs no
Stripe dashboard change (FR-016). The session carries the payment id in its metadata and the
user id as ``client_reference_id``. The checkout request uses an idempotency key derived from
the payment id, so the SDK's retry can never create a second session.

Timeouts and retries (contract section 6): ``STRIPE_TIMEOUT_SECONDS`` (10 s) per call and
``STRIPE_MAX_NETWORK_RETRIES`` (1). Any Stripe failure becomes :class:`GatewayError`, which
the service maps to 502 ``UPSTREAM_UNAVAILABLE`` (504 ``UPSTREAM_TIMEOUT`` on a timeout); the
user is never charged by a failed checkout. No secret or personal data is logged.
"""

from __future__ import annotations

import logging
from typing import Any

import stripe

from app.payments.gateway import (
    CheckoutRequest,
    CheckoutSession,
    GatewayError,
    WebhookEvent,
    verify_and_parse,
)

logger = logging.getLogger("payments.stripe")


class StripeGateway:
    """Hosted Checkout and webhook verification through the official Stripe SDK.

    Args:
        secret_key: ``STRIPE_SECRET_KEY``.
        webhook_secret: ``STRIPE_WEBHOOK_SECRET`` (``whsec_...``).
        timeout_seconds: Per-request timeout.
        max_network_retries: SDK retries for connection errors and timeouts.
        http_client: The SDK HTTP client; tests pass a stub. Default: ``requests`` with the
            timeout above.
    """

    name = "stripe"

    def __init__(
        self,
        *,
        secret_key: str,
        webhook_secret: str,
        timeout_seconds: float,
        max_network_retries: int,
        http_client: stripe.HTTPClient | None = None,
    ) -> None:
        self._webhook_secret = webhook_secret
        self._client = stripe.StripeClient(
            secret_key,
            max_network_retries=max_network_retries,
            http_client=http_client or stripe.RequestsClient(timeout=timeout_seconds),
        )

    @staticmethod
    def checkout_params(request: CheckoutRequest) -> dict[str, Any]:
        """The ``checkout.sessions.create`` parameters for one one-time payment."""
        metadata = {"payment_id": str(request.payment_id), "user_id": str(request.user_id)}
        return {
            "mode": "payment",
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": request.currency.lower(),
                        "unit_amount": request.amount,
                        "product_data": {"name": request.description},
                    },
                }
            ],
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "client_reference_id": str(request.user_id),
            "metadata": metadata,
            "payment_intent_data": {"metadata": metadata},
        }

    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        """Create the hosted Checkout session.

        Raises:
            GatewayError: When Stripe fails, times out, or returns no session URL.
        """
        try:
            session = self._client.v1.checkout.sessions.create(
                params=self.checkout_params(request),  # type: ignore[arg-type]
                options={"idempotency_key": f"checkout-{request.payment_id}"},
            )
        except stripe.APIConnectionError as exc:
            timed_out = "Timeout" in str(exc)
            logger.warning(
                "stripe checkout failed",
                extra={"event": "payments.stripe.unavailable", "timeout": timed_out},
            )
            raise GatewayError("stripe connection error", timeout=timed_out) from None
        except stripe.StripeError as exc:
            logger.warning(
                "stripe checkout failed",
                extra={"event": "payments.stripe.error", "errorClass": type(exc).__name__},
            )
            raise GatewayError("stripe error") from None
        if not session.id or not session.url:
            raise GatewayError("stripe returned a session without a URL")
        return CheckoutSession(session_id=session.id, url=session.url)

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> WebhookEvent:
        """Verify Stripe's signature against the raw body and parse the event."""
        return verify_and_parse(raw_body, signature, self._webhook_secret)
