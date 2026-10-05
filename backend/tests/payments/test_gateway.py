"""Webhook signing, verification against the raw body, and event parsing (US6.3; AC6.3.3)."""

from __future__ import annotations

import json
import time
import uuid

import pytest

from app.payments.gateway import (
    ASYNC_FAILED,
    ASYNC_SUCCEEDED,
    COMPLETED,
    EXPIRED,
    WebhookEvent,
    WebhookVerificationError,
    parse_event,
    sign_payload,
    verify_and_parse,
)

SECRET = "whsec_unit_test"


def event_body(
    event_type: str = COMPLETED, payment_status: str = "paid", payment_id: str | None = None
) -> bytes:
    return json.dumps(
        {
            "id": "evt_1",
            "type": event_type,
            "data": {
                "object": {
                    "id": "cs_1",
                    "payment_status": payment_status,
                    "metadata": {"payment_id": payment_id or str(uuid.uuid4())},
                }
            },
        }
    ).encode()


def test_a_correctly_signed_event_is_verified_and_parsed() -> None:
    body = event_body()
    event = verify_and_parse(body, sign_payload(body, SECRET, int(time.time())), SECRET)
    assert event.event_id == "evt_1"
    assert event.event_type == COMPLETED
    assert event.session_id == "cs_1"
    assert event.payment_status == "paid"
    assert isinstance(event.payment_id, uuid.UUID)
    assert event.is_success
    assert not event.is_failure


@pytest.mark.parametrize(
    "signature",
    [
        None,
        "",
        "garbage",
        "t=1,v1=" + "0" * 64,
    ],
)
def test_missing_malformed_or_wrong_signatures_are_rejected(signature: str | None) -> None:
    with pytest.raises(WebhookVerificationError) as caught:
        verify_and_parse(event_body(), signature, SECRET)
    assert caught.value.reason == "SIGNATURE_INVALID"


def test_the_signature_covers_the_raw_bytes_exactly() -> None:
    body = event_body()
    signature = sign_payload(body, SECRET, int(time.time()))
    reformatted = json.dumps(json.loads(body), indent=2).encode()  # same JSON, other bytes
    with pytest.raises(WebhookVerificationError):
        verify_and_parse(reformatted, signature, SECRET)
    with pytest.raises(WebhookVerificationError):
        verify_and_parse(body, signature, "whsec_another_secret")


def test_a_stale_signature_is_rejected() -> None:
    body = event_body()
    old = sign_payload(body, SECRET, int(time.time()) - 3600)
    with pytest.raises(WebhookVerificationError) as caught:
        verify_and_parse(body, old, SECRET)
    assert caught.value.reason == "SIGNATURE_INVALID"


@pytest.mark.parametrize(
    "body",
    [b"not json", b"[1, 2]", b'{"type": "x"}', b'{"id": "evt_1"}', b'{"id": 5, "type": "x"}'],
)
def test_signed_bodies_that_are_not_events_are_unreadable(body: bytes) -> None:
    with pytest.raises(WebhookVerificationError) as caught:
        verify_and_parse(body, sign_payload(body, SECRET, int(time.time())), SECRET)
    assert caught.value.reason == "PAYLOAD_UNREADABLE"


def test_parse_tolerates_missing_session_fields() -> None:
    event = parse_event(b'{"id": "evt_2", "type": "customer.created", "data": {"object": []}}')
    assert event == WebhookEvent("evt_2", "customer.created", None, None, None)
    assert parse_event(event_body(payment_id="not-a-uuid")).payment_id is None


@pytest.mark.parametrize(
    ("event_type", "payment_status", "success", "failure"),
    [
        (COMPLETED, "paid", True, False),
        (COMPLETED, "unpaid", False, False),  # an async method completes unpaid first
        (ASYNC_SUCCEEDED, "paid", True, False),
        (ASYNC_FAILED, "unpaid", False, True),
        (EXPIRED, "unpaid", False, True),
        ("payment_intent.created", "paid", False, False),
    ],
)
def test_event_outcomes(event_type: str, payment_status: str, success: bool, failure: bool) -> None:
    event = WebhookEvent("evt", event_type, "cs", None, payment_status)
    assert event.is_success is success
    assert event.is_failure is failure
