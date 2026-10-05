"""FastAPI dependencies for payment routes."""

from __future__ import annotations

from fastapi import Request, Response

from app.payments.services import PaymentService


def get_payments(request: Request) -> PaymentService:
    """The payments service wired by the app factory."""
    service: PaymentService = request.app.state.payments
    return service


def no_store(response: Response) -> None:
    """Payment state is personal: never let a browser or proxy cache it."""
    response.headers["Cache-Control"] = "no-store"


async def raw_body(request: Request) -> bytes:
    """The request body exactly as received: the webhook signature covers these bytes."""
    return await request.body()
