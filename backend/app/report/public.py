"""The Report module's public interface. Other modules import only this.

- ``build_report``: the service from the payment service and the media store.
- ``router``: ``/report``, ``/report/pdf`` and ``/home`` (mounted as protected routes).
"""

from __future__ import annotations

from app.media.public import MediaStore
from app.payments.public import PaymentService
from app.platform.clock import Clock
from app.report.routes import router
from app.report.service import ReportService

__all__ = ["ReportService", "build_report", "router"]


def build_report(*, payments: PaymentService, media: MediaStore, clock: Clock) -> ReportService:
    """Create the report service."""
    return ReportService(payments=payments, media=media, clock=clock)
