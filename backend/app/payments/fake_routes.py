"""The fake provider's hosted test page (development and test only; U5 plan Step 3).

Mounted by the app factory only when ``PAYMENT_PROVIDER=fake`` (which settings refuse outside
development and test), and left out of the OpenAPI document. The paths are listed in
``FAKE_PAYMENT_ROUTES`` (route classes): they need no access token because the browser
navigates to them, as it would to Stripe's own hosted page. They only ever act on a session
the fake recorded.

- ``GET  /payments/fake-checkout/{sessionId}``: a small page with the amount, "Pay" and
  "Cancel";
- ``POST /payments/fake-checkout/{sessionId}/pay``: delivers the signed
  ``checkout.session.completed`` webhook and redirects (303) to the success URL;
- ``POST /payments/fake-checkout/{sessionId}/cancel``: redirects (303) to the cancel URL;
  nothing is charged and no event is sent.
"""

from __future__ import annotations

from html import escape
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.payments.fake_gateway import FAKE_SESSION_PATTERN, FakePaymentGateway, FakeSession
from app.platform.errors import NotFound

SessionIdPath = Annotated[str, Path(pattern=FAKE_SESSION_PATTERN)]

fake_checkout_router = APIRouter(include_in_schema=False)


def _fake(request: Request) -> FakePaymentGateway:
    gateway = request.app.state.payment_gateway
    if not isinstance(gateway, FakePaymentGateway):  # mounted only for the fake
        raise NotFound()
    return gateway


def _page(recorded: FakeSession) -> str:
    request = recorded.request
    # A test page: the amount is shown with two decimals plus the exact minor units.
    amount = f"{request.amount / 100:.2f} {escape(request.currency)}"
    base = f"/payments/fake-checkout/{escape(recorded.session_id)}"
    status = "This test session is already paid." if recorded.paid else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test checkout (fake payment provider)</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 0; padding: 24px; color: #1a1a1a; }}
main {{ max-width: 420px; margin: 0 auto; }}
button {{ min-height: 44px; padding: 0 20px; font-size: 16px; margin-right: 12px; }}
.pay {{ background: #1d5c54; color: #fff; border: 0; border-radius: 6px; }}
.cancel {{ background: #fff; color: #1a1a1a; border: 1px solid #555; border-radius: 6px; }}
</style>
</head>
<body>
<main>
<h1>Test checkout</h1>
<p>This is the fake payment provider used in development and tests. No real money moves.</p>
<p>Amount due: <strong data-testid="fake-checkout-amount">{amount}</strong>
(<span data-testid="fake-checkout-minor-units">{request.amount}</span> minor units)</p>
<p data-testid="fake-checkout-status">{status}</p>
<form method="post" action="{base}/pay" style="display:inline">
<button class="pay" type="submit" data-testid="fake-checkout-pay">Pay</button>
</form>
<form method="post" action="{base}/cancel" style="display:inline">
<button class="cancel" type="submit" data-testid="fake-checkout-cancel">Cancel</button>
</form>
</main>
</body>
</html>
"""


@fake_checkout_router.get("/payments/fake-checkout/{session_id}", response_class=HTMLResponse)
def fake_checkout_page(session_id: SessionIdPath, request: Request) -> HTMLResponse:
    """The hosted test page for a recorded session (404 otherwise)."""
    recorded = _fake(request).session(session_id)
    if recorded is None:
        raise NotFound("This test checkout session doesn't exist.")
    return HTMLResponse(_page(recorded), headers={"Cache-Control": "no-store"})


@fake_checkout_router.post("/payments/fake-checkout/{session_id}/pay")
def fake_checkout_pay(session_id: SessionIdPath, request: Request) -> RedirectResponse:
    """Pay: deliver the signed webhook, then return to the success URL (303)."""
    target = _fake(request).pay(session_id)
    if target is None:
        raise NotFound("This test checkout session doesn't exist.")
    return RedirectResponse(target, status_code=303)


@fake_checkout_router.post("/payments/fake-checkout/{session_id}/cancel")
def fake_checkout_cancel(session_id: SessionIdPath, request: Request) -> RedirectResponse:
    """Cancel: return to the cancel URL (303); nothing is charged."""
    target = _fake(request).cancel(session_id)
    if target is None:
        raise NotFound("This test checkout session doesn't exist.")
    return RedirectResponse(target, status_code=303)
