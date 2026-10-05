"""Payments service: the offer, checkout, the webhook, and the paywall (contract C5).

FR-015, FR-016, BR-001, FR7.1-FR7.6; US6.1-US6.5.

Plan decisions ([Decided by delivery team] unless noted):

- **Offer.** Price and currency come from configuration (``REPORT_PRICE_AMOUNT`` in minor
  units, ``REPORT_PRICE_CURRENCY``); nothing is hard-coded (FR-016, OQ-002). The list of what
  payment unlocks is [Recommendation: copy] (AC6.1.2).
- **Checkout order.** 409 ``ALREADY_PAID`` after a successful payment (one payment per report,
  FR7.2); then the same-person re-check from the photos stored now (U4 port, BR-005): 409
  ``PHOTO_SET_INCOMPLETE``, or 409 ``PHOTO_IDENTITY_MISMATCH`` naming exactly the angles the
  U4 function flags (AC6.2.2). Only then is a ``pending`` payment committed, the provider
  called outside any transaction (NFR5.13), and the session id stored. A provider failure
  marks the attempt ``failed`` and answers 502/504; nothing is charged.
- **Webhook.** Signature verified against the raw body before parsing (AC6.3.3); the event
  id is recorded under a unique constraint first, so a repeated or concurrent delivery
  changes nothing twice (AC6.3.2). ``checkout.session.completed`` with ``payment_status=paid``
  or ``async_payment_succeeded`` marks the payment ``succeeded``; ``async_payment_failed`` or
  ``expired`` marks a still-pending payment ``failed``. The webhook NEVER starts analysis
  (FR-015, FR7.4): it only records the payment. 200 is answered only after the commit.
- **Status changes only through the webhook** (FR7.4); the success redirect is never trusted.
- **Paywall.** :meth:`PaymentService.require_paid` raises 402 ``PAYMENT_REQUIRED``. Callers
  (U6 "Start Analysis", U8 report) check it BEFORE the photo set (AC6.4.2, contract C11
  precedence).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.payments import repositories
from app.payments.gateway import (
    CheckoutRequest,
    CheckoutSession,
    GatewayError,
    PaymentGateway,
    WebhookEvent,
    WebhookVerificationError,
)
from app.payments.models import Payment, PaymentStatus
from app.photos.public import IdentityResult
from app.platform.clock import Clock
from app.platform.errors import (
    AlreadyPaid,
    PaymentRequired,
    PhotoIdentityMismatch,
    PhotoSetIncomplete,
    UpstreamTimeout,
    UpstreamUnavailable,
    WebhookRejected,
)

logger = logging.getLogger("payments")

#: The same-person check over the photos stored now (U4 port ``check_identity``).
IdentityCheck = Callable[[Session, uuid.UUID], IdentityResult]
PaymentState = Literal["none", "pending", "paid"]
WebhookOutcome = Literal["processed", "duplicate", "unknown_session"]

#: What payment unlocks (AC6.1.2). [Recommendation: copy]
OFFER_INCLUDES: tuple[str, ...] = (
    "Your full facial analysis report covering 11 features, with a PDF to download",
    "AI-generated visuals of suggested looks",
    "The AI Beauty Assistant, answering questions about your report",
)
PRODUCT_DESCRIPTION = "AI facial analysis report"
CHECKOUT_UNAVAILABLE = "We couldn't reach the payment service. You have not been charged."


@dataclass(frozen=True)
class Price:
    """The configured report price (minor units) and ISO currency code."""

    amount: int
    currency: str


@dataclass(frozen=True)
class Offer:
    """``GET /payments/offer`` (contract C1 ``Offer``)."""

    amount: int
    currency: str
    includes: tuple[str, ...]


@dataclass(frozen=True)
class PaymentStatusView:
    """``GET /payments/status`` (contract C1 ``PaymentStatus``)."""

    state: PaymentState
    paid_at: datetime | None


@dataclass(frozen=True)
class Entitlement:
    """Contract C5 ``entitlement``: has the user paid, and with which payment."""

    paid: bool
    payment_id: uuid.UUID | None


class PaymentService:
    """Payment use cases. Public methods that change data commit their own transaction.

    Args:
        gateway: The configured payment provider adapter (Stripe or the fake).
        clock: Time source.
        identity_check: The U4 same-person check (C4 ``check_identity``).
        price: The configured price.
        success_url: Where the provider sends the user after paying.
        cancel_url: Where the provider sends the user after cancelling.
        confirm_wait_seconds: The "still confirming" wait shown by the web app (AC6.5.3).
    """

    def __init__(
        self,
        *,
        gateway: PaymentGateway,
        clock: Clock,
        identity_check: IdentityCheck,
        price: Price,
        success_url: str,
        cancel_url: str,
        confirm_wait_seconds: int,
    ) -> None:
        self.gateway = gateway
        self.clock = clock
        self.identity_check = identity_check
        self.price = price
        self.success_url = success_url
        self.cancel_url = cancel_url
        self.confirm_wait_seconds = confirm_wait_seconds

    # --- Reading -------------------------------------------------------------------------

    def offer(self) -> Offer:
        """The configured price and what it unlocks (FR7.1, FR7.3)."""
        return Offer(self.price.amount, self.price.currency, OFFER_INCLUDES)

    def entitlement(self, session: Session, user_id: uuid.UUID) -> Entitlement:
        """Whether the user has a successful payment (C5 ``entitlement``)."""
        paid = repositories.find_succeeded(session, user_id)
        return Entitlement(paid=paid is not None, payment_id=paid.id if paid else None)

    def status(self, session: Session, user_id: uuid.UUID) -> PaymentStatusView:
        """``paid`` once a payment succeeded; ``pending`` while the latest attempt waits."""
        paid = repositories.find_succeeded(session, user_id)
        if paid is not None:
            return PaymentStatusView(state="paid", paid_at=paid.paid_at)
        latest = repositories.find_latest(session, user_id)
        if latest is not None and latest.status == PaymentStatus.PENDING:
            return PaymentStatusView(state="pending", paid_at=None)
        return PaymentStatusView(state="none", paid_at=None)

    def payment_state(self, session: Session, user_id: uuid.UUID) -> PaymentState:
        """``none`` / ``pending`` / ``paid`` for the Journey (C5 ``payment_state``)."""
        return self.status(session, user_id).state

    def require_paid(self, session: Session, user_id: uuid.UUID) -> Entitlement:
        """The paywall (FR-015, BR-001, FR7.6).

        Raises:
            PaymentRequired: 402 when no payment has succeeded.
        """
        entitlement = self.entitlement(session, user_id)
        if not entitlement.paid:
            raise PaymentRequired()
        return entitlement

    # --- Checkout ----------------------------------------------------------------------------

    def _require_consistent_photos(self, session: Session, user_id: uuid.UUID) -> None:
        result = self.identity_check(session, user_id)
        if result.status == "incomplete":
            raise PhotoSetIncomplete()
        if result.status == "mismatch":
            raise PhotoIdentityMismatch(result.mismatched_angles)

    def start_checkout(self, session: Session, user_id: uuid.UUID) -> CheckoutSession:
        """Create a hosted Checkout session for the configured price (US6.2).

        Raises:
            AlreadyPaid: 409 after a successful payment.
            PhotoSetIncomplete: 409 when an angle has no accepted photo.
            PhotoIdentityMismatch: 409 naming the flagged angles (AC6.2.2).
            UpstreamUnavailable: 502 when the provider fails.
            UpstreamTimeout: 504 when the provider does not answer in time.
        """
        if self.entitlement(session, user_id).paid:
            raise AlreadyPaid()
        self._require_consistent_photos(session, user_id)

        now = self.clock.now()
        payment = repositories.add_payment(
            session,
            Payment(
                id=uuid.uuid4(),
                user_id=user_id,
                provider=self.gateway.name,
                provider_session_id=None,
                amount=self.price.amount,
                currency=self.price.currency,
                status=PaymentStatus.PENDING.value,
                created_at=now,
                updated_at=now,
                paid_at=None,
            ),
        )
        session.commit()  # no transaction spans the provider call (NFR5.13)

        request = CheckoutRequest(
            payment_id=payment.id,
            user_id=user_id,
            amount=payment.amount,
            currency=payment.currency,
            success_url=self.success_url,
            cancel_url=self.cancel_url,
            description=PRODUCT_DESCRIPTION,
        )
        try:
            checkout = self.gateway.create_checkout(request)
        except GatewayError as exc:
            self._mark_failed_attempt(session, payment.id)
            if exc.timeout:
                raise UpstreamTimeout(CHECKOUT_UNAVAILABLE) from None
            raise UpstreamUnavailable(CHECKOUT_UNAVAILABLE) from None

        locked = repositories.lock_by_id(session, payment.id)
        if locked is not None:
            locked.provider_session_id = checkout.session_id
            locked.updated_at = self.clock.now()
        session.commit()
        logger.info(
            "checkout created",
            extra={
                "event": "payments.checkout.created",
                "paymentId": str(payment.id),
                "provider": self.gateway.name,
                "amount": payment.amount,
                "currency": payment.currency,
            },
        )
        return checkout

    def _mark_failed_attempt(self, session: Session, payment_id: uuid.UUID) -> None:
        locked = repositories.lock_by_id(session, payment_id)
        if locked is not None and locked.status == PaymentStatus.PENDING:
            locked.status = PaymentStatus.FAILED.value
            locked.updated_at = self.clock.now()
        session.commit()

    # --- Webhook -----------------------------------------------------------------------------

    def _locate(self, session: Session, event: WebhookEvent) -> Payment | None:
        payment = (
            repositories.lock_by_session_id(session, event.session_id) if event.session_id else None
        )
        if payment is None and event.payment_id is not None:
            # The webhook can arrive before the session id is stored: use the metadata.
            payment = repositories.lock_by_id(session, event.payment_id)
        return payment

    def _apply(self, payment: Payment, event: WebhookEvent, now: datetime) -> None:
        if event.is_success and payment.status != PaymentStatus.SUCCEEDED:
            payment.status = PaymentStatus.SUCCEEDED.value
            payment.paid_at = now
            payment.updated_at = now
            logger.info(
                "payment succeeded",
                extra={"event": "payments.payment.succeeded", "paymentId": str(payment.id)},
            )
        elif event.is_failure and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.FAILED.value
            payment.updated_at = now
            logger.info(
                "payment failed",
                extra={"event": "payments.payment.failed", "paymentId": str(payment.id)},
            )

    def handle_webhook(
        self, session: Session, raw_body: bytes, signature: str | None
    ) -> WebhookOutcome:
        """Verify, de-duplicate and apply one provider event (US6.3). Never starts analysis.

        Raises:
            WebhookRejected: 400 when the signature or body is invalid; nothing changes.
        """
        try:
            event = self.gateway.verify_webhook(raw_body, signature)
        except WebhookVerificationError as exc:
            logger.warning(
                "webhook rejected",
                extra={"event": "payments.webhook.rejected", "reason": exc.reason},
            )
            raise WebhookRejected(exc.reason) from None

        now = self.clock.now()
        event_row_id = repositories.record_event(session, event.event_id, event.event_type, now)
        if event_row_id is None:
            session.rollback()
            logger.info(
                "webhook duplicate ignored",
                extra={"event": "payments.webhook.duplicate", "eventType": event.event_type},
            )
            return "duplicate"

        payment = self._locate(session, event)
        if payment is None:
            session.commit()  # remember the event id so a retry is still a duplicate
            logger.warning(
                "webhook for an unknown session",
                extra={"event": "payments.webhook.unknown", "eventType": event.event_type},
            )
            return "unknown_session"
        repositories.link_event(session, event_row_id, payment.id)
        self._apply(payment, event, now)
        session.commit()
        return "processed"
