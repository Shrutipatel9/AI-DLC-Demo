"""Response models for ``/settings/*`` (camelCase JSON)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AccountOut(CamelModel):
    """``GET /settings/account``: name, email, verification status and member-since (FR13.1)."""

    full_name: str
    email: str
    is_verified: bool
    member_since: datetime


class PaymentRecordOut(CamelModel):
    """One payment (contract C1 ``PaymentRecord``)."""

    date: datetime
    amount: int
    currency: str
    status: Literal["pending", "succeeded", "failed"]


class BillingOut(CamelModel):
    """``GET /settings/billing``: the payment history, newest first (FR13.3)."""

    payments: list[PaymentRecordOut]
