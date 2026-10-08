"""The Payments module's public interface (contract C5). Other modules import only this.

- ``build_payment_gateway`` / ``build_payments``: wire the provider adapter and the service
  from settings (used by the app factory).
- ``router`` (protected ``/payments/*``), ``webhook_router`` (public webhook) and
  ``fake_checkout_router`` (the fake provider's test page; development/test only).
- ``entitlement`` / ``payment_state``: C5 reads for U6, U8 and the Journey (U10).
- ``require_paid``: the paywall, 402 ``PAYMENT_REQUIRED`` (FR-015, BR-001, FR7.6).
- ``paid_photo_snapshot``: what "Start Analysis" (U6) must call: payment FIRST (402), then the
  photo set's consistent snapshot (409), the precedence of contract C11 (AC6.4.2). A set that
  failed validation therefore never reaches the analysis (AC6.4.3).
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy.orm import Session

from app.payments.fake_gateway import WEBHOOK_PATH, FakePaymentGateway, HttpWebhookDeliverer
from app.payments.fake_routes import fake_checkout_router
from app.payments.gateway import PaymentGateway
from app.payments.routes import router, webhook_router
from app.payments.services import (
    Entitlement,
    IdentityCheck,
    PaymentRecordView,
    PaymentService,
    PaymentState,
    Price,
)
from app.payments.stripe_gateway import StripeGateway
from app.photos.public import PhotoIntakeService, snapshot_for_run
from app.platform.clock import Clock
from app.platform.settings import Settings

__all__ = [
    "Entitlement",
    "PaymentGateway",
    "PaymentRecordView",
    "PaymentService",
    "PaymentState",
    "build_payment_gateway",
    "build_payments",
    "entitlement",
    "fake_checkout_router",
    "paid_photo_snapshot",
    "payment_history",
    "payment_state",
    "require_paid",
    "router",
    "webhook_router",
]


def build_payment_gateway(settings: Settings) -> PaymentGateway:
    """The adapter chosen by ``PAYMENT_PROVIDER`` (ADR-005).

    The fake signs with ``STRIPE_WEBHOOK_SECRET`` when set, otherwise with a random secret
    for this process, and posts its webhooks to ``FAKE_PAYMENT_BASE_URL``.
    """
    if settings.payment_provider == "fake":
        secret = (
            settings.stripe_webhook_secret.get_secret_value()
            if settings.stripe_webhook_secret is not None
            else "whsec_fake_" + secrets.token_hex(24)
        )
        deliverer = HttpWebhookDeliverer(
            settings.fake_payment_base_url + WEBHOOK_PATH,
            settings.fake_payment_webhook_delay_seconds,
        )
        return FakePaymentGateway(
            webhook_secret=secret, base_url=settings.fake_payment_base_url, deliver=deliverer
        )
    # Settings guarantee both secrets when the provider is Stripe.
    assert settings.stripe_secret_key is not None  # noqa: S101
    assert settings.stripe_webhook_secret is not None  # noqa: S101
    return StripeGateway(
        secret_key=settings.stripe_secret_key.get_secret_value(),
        webhook_secret=settings.stripe_webhook_secret.get_secret_value(),
        timeout_seconds=settings.stripe_timeout_seconds,
        max_network_retries=settings.stripe_max_network_retries,
    )


def build_payments(
    settings: Settings,
    *,
    clock: Clock,
    gateway: PaymentGateway,
    identity_check: IdentityCheck,
) -> PaymentService:
    """Create the payments service from settings and its collaborators."""
    success_url, cancel_url = settings.payment_return_urls
    return PaymentService(
        gateway=gateway,
        clock=clock,
        identity_check=identity_check,
        price=Price(settings.report_price_amount, settings.report_price_currency),
        success_url=success_url,
        cancel_url=cancel_url,
        confirm_wait_seconds=settings.payment_confirm_wait_seconds,
    )


def entitlement(service: PaymentService, session: Session, user_id: uuid.UUID) -> Entitlement:
    """Has the user paid, and with which payment (C5 ``entitlement``)."""
    return service.entitlement(session, user_id)


def payment_state(service: PaymentService, session: Session, user_id: uuid.UUID) -> PaymentState:
    """``none`` / ``pending`` / ``paid`` (C5 ``payment_state``)."""
    return service.payment_state(session, user_id)


def payment_history(
    service: PaymentService, session: Session, user_id: uuid.UUID
) -> list[PaymentRecordView]:
    """The user's payments, newest first (Settings -> Billing, US11.6)."""
    return service.history(session, user_id)


def require_paid(service: PaymentService, session: Session, user_id: uuid.UUID) -> Entitlement:
    """The paywall.

    Raises:
        app.platform.errors.PaymentRequired: 402 when no payment has succeeded.
    """
    return service.require_paid(session, user_id)


def paid_photo_snapshot(
    payments: PaymentService,
    photos: PhotoIntakeService,
    session: Session,
    user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """Payment first (402), then the consistent photo set's file ids (409; AC6.4.2, AC6.4.3).

    Raises:
        app.platform.errors.PaymentRequired: 402 when no payment has succeeded.
        app.platform.errors.PhotoSetIncomplete: 409 when an angle has no accepted photo.
        app.platform.errors.PhotoIdentityMismatch: 409 when the same-person check fails.
    """
    payments.require_paid(session, user_id)
    return snapshot_for_run(photos, session, user_id)
