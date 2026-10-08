"""``/settings/account`` and ``/settings/billing`` (US11.4, US11.6): protected, owner-only.

Both answer only for the verified token's own user; there is no id in the path to tamper
with. Responses are never cached.
"""

from __future__ import annotations

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, IdentityService, current_user
from app.payments.public import PaymentService, payment_history
from app.platform.db import get_session
from app.platform.errors import error_responses
from app.settings.schemas import AccountOut, BillingOut, PaymentRecordOut

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]


def no_store(response: Response) -> None:
    """Account and billing data are personal: never cache them."""
    response.headers["Cache-Control"] = "no-store"


def _identity(request: Request) -> IdentityService:
    service: IdentityService = request.app.state.identity
    return service


def _payments(request: Request) -> PaymentService:
    service: PaymentService = request.app.state.payments
    return service


IdentityDep = Annotated[IdentityService, Depends(_identity)]
PaymentsDep = Annotated[PaymentService, Depends(_payments)]

router = APIRouter(tags=["settings"], dependencies=[Depends(no_store)])


@router.get(
    "/settings/account",
    response_model=AccountOut,
    response_model_by_alias=True,
    responses=error_responses(401),
    summary="Account Info: name, email, verification status, member-since (US11.4)",
)
def get_account(user: UserDep, session: SessionDep, identity: IdentityDep) -> AccountOut:
    """The caller's own account; the name has no edit endpoint (AC11.4.2)."""
    account = identity.account(session, user.user_id)
    return AccountOut(
        full_name=account.full_name,
        email=account.email,
        is_verified=account.is_verified,
        member_since=account.member_since,
    )


@router.get(
    "/settings/billing",
    response_model=BillingOut,
    response_model_by_alias=True,
    responses=error_responses(401),
    summary="Billing: the caller's payments with date, amount, currency, status (US11.6)",
)
def get_billing(user: UserDep, session: SessionDep, payments: PaymentsDep) -> BillingOut:
    """The caller's own payments, newest first."""
    rows = payment_history(payments, session, user.user_id)
    return BillingOut(
        payments=[
            PaymentRecordOut(
                date=row.date,
                amount=row.amount,
                currency=row.currency,
                status=cast(Literal["pending", "succeeded", "failed"], row.status),
            )
            for row in rows
        ]
    )
