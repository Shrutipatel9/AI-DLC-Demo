"""Response models for ``/payments/*`` (contract C1 Offer and PaymentStatus; camelCase JSON).

Additive to C1 [Decided by delivery team]: ``confirmWaitSeconds`` on PaymentStatus (the
configured wait before the "still confirming" message, AC6.5.3) and the webhook's
``{"received": true}`` body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class OfferOut(CamelModel):
    """``GET /payments/offer``: the configured price and what payment unlocks (FR7.1, FR7.3)."""

    #: Minor units (cents), from configuration (FR-016).
    amount: int
    #: ISO 4217 code, upper-case.
    currency: str
    includes: list[str]


class CheckoutOut(CamelModel):
    """``POST /payments/checkout``: the hosted Checkout URL to send the browser to."""

    checkout_url: str


class PaymentStatusOut(CamelModel):
    """``GET /payments/status``: polled by the "confirming your payment" screen (US6.5)."""

    state: Literal["none", "pending", "paid"]
    paid_at: datetime | None = None
    confirm_wait_seconds: int


class WebhookReceived(BaseModel):
    """The webhook's 200 body (processed, or already processed)."""

    received: bool = True
