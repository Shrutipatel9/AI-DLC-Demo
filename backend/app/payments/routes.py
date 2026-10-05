"""Payment HTTP routes (contract C1 ``/payments``, contract C2 webhook; US6.1-US6.5).

- ``router`` (protected; mounted with ``current_user``; ``Cache-Control: no-store``):
  ``GET /payments/offer``, ``POST /payments/checkout``, ``GET /payments/status``.
- ``webhook_router`` (public; in ``PUBLIC_ROUTES``): ``POST /payments/stripe/webhook``. It is
  authenticated by the provider's signature over the raw body, needs no access token and no
  CSRF check (it is not a browser endpoint), and answers 200 only after the commit.

Handlers stay thin and call :class:`PaymentService`; they never touch repositories or models.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.payments.dependencies import get_payments, no_store, raw_body
from app.payments.schemas import CheckoutOut, OfferOut, PaymentStatusOut, WebhookReceived
from app.payments.services import PaymentService
from app.platform.db import get_session
from app.platform.errors import error_responses

SessionDep = Annotated[Session, Depends(get_session)]
PaymentsDep = Annotated[PaymentService, Depends(get_payments)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]

WEBHOOK_PATH = "/payments/stripe/webhook"

router = APIRouter(tags=["payments"], dependencies=[Depends(no_store)])
webhook_router = APIRouter(tags=["payments"])


@router.get(
    "/payments/offer",
    response_model=OfferOut,
    response_model_by_alias=True,
    responses=error_responses(401),
    summary="Price, currency and what payment unlocks (from configuration)",
)
def get_offer(payments: PaymentsDep) -> OfferOut:
    """Return the configured offer (US6.1; FR7.1, FR7.3)."""
    offer = payments.offer()
    return OfferOut(amount=offer.amount, currency=offer.currency, includes=list(offer.includes))


@router.post(
    "/payments/checkout",
    status_code=201,
    response_model=CheckoutOut,
    response_model_by_alias=True,
    responses=error_responses(401, 409, 502, 504),
    summary="Creates a Stripe hosted Checkout session after the same-person re-check",
)
def post_checkout(user: UserDep, session: SessionDep, payments: PaymentsDep) -> CheckoutOut:
    """409 ``ALREADY_PAID`` / ``PHOTO_SET_INCOMPLETE`` / ``PHOTO_IDENTITY_MISMATCH`` (US6.2)."""
    checkout = payments.start_checkout(session, user.user_id)
    return CheckoutOut(checkout_url=checkout.url)


@router.get(
    "/payments/status",
    response_model=PaymentStatusOut,
    response_model_by_alias=True,
    responses=error_responses(401),
    summary="Payment state for the confirming screen (polled every 2-3 s)",
)
def get_status(user: UserDep, session: SessionDep, payments: PaymentsDep) -> PaymentStatusOut:
    """``none`` / ``pending`` / ``paid`` (US6.5); changes only through the webhook."""
    view = payments.status(session, user.user_id)
    return PaymentStatusOut(
        state=view.state,
        paid_at=view.paid_at,
        confirm_wait_seconds=payments.confirm_wait_seconds,
    )


@webhook_router.post(
    WEBHOOK_PATH,
    response_model=WebhookReceived,
    responses=error_responses(400),
    summary="Receives Stripe events; the only way a payment's status changes (FR-015)",
)
def post_webhook(
    body: Annotated[bytes, Depends(raw_body)],
    session: SessionDep,
    payments: PaymentsDep,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> WebhookReceived:
    """Verify against the raw body, record once, never start analysis (US6.3; FR7.4, FR7.5)."""
    payments.handle_webhook(session, body, stripe_signature)
    return WebhookReceived()
