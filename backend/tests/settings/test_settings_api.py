"""Settings -> Account Info and Billing through the real API (US11.4, US11.6, FR13.1, FR13.3)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.payments.models import PaymentStatus
from app.platform.clock import FrozenClock
from tests.factories import SignedInUser
from tests.identity.conftest import bearer
from tests.journey.conftest import insert_payment


def get(client: TestClient, path: str, user: SignedInUser) -> Any:
    return client.get(path, headers=bearer(user.access_token))


def test_account_info_has_name_email_verification_and_member_since(
    client: TestClient, user: SignedInUser
) -> None:
    """AC11.4.1."""
    response = get(client, "/settings/account", user)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["fullName"] == user.full_name
    assert body["email"] == user.email
    assert body["isVerified"] is True
    assert body["memberSince"]
    assert set(body) == {"fullName", "email", "isVerified", "memberSince"}


def test_there_is_no_endpoint_to_edit_the_name(client: TestClient, user: SignedInUser) -> None:
    """AC11.4.2: the name is not editable, so no write method exists on the account route."""
    for method in ("put", "patch", "post", "delete"):
        response = getattr(client, method)("/settings/account", headers=bearer(user.access_token))
        assert response.status_code == 405


def test_settings_need_a_token(client: TestClient) -> None:
    assert client.get("/settings/account").status_code == 401
    assert client.get("/settings/billing").status_code == 401


def test_billing_lists_my_payments_newest_first_with_date_amount_currency_status(
    client: TestClient, user: SignedInUser, db_session: Session, frozen_clock: FrozenClock
) -> None:
    """AC11.6.1."""
    assert get(client, "/settings/billing", user).json() == {"payments": []}
    insert_payment(
        db_session, user.user_id, now=frozen_clock.now(), status=PaymentStatus.FAILED, amount=2900
    )
    frozen_clock.advance(seconds=60)
    insert_payment(
        db_session,
        user.user_id,
        now=frozen_clock.now(),
        status=PaymentStatus.SUCCEEDED,
        amount=2900,
    )

    response = get(client, "/settings/billing", user)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    rows = response.json()["payments"]
    assert [row["status"] for row in rows] == ["succeeded", "failed"]
    assert rows[0]["amount"] == 2900
    assert rows[0]["currency"] == "USD"
    assert rows[0]["date"]


def test_billing_never_shows_another_users_payments(
    client: TestClient,
    user: SignedInUser,
    paid: SignedInUser,
) -> None:
    """Owner-only: the paid user has a payment; this user sees none."""
    assert len(get(client, "/settings/billing", paid).json()["payments"]) == 1
    assert get(client, "/settings/billing", user).json()["payments"] == []
