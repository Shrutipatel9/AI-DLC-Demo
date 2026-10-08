"""Report use cases: the report, the Home data and the cached PDF (US8.1, US8.5, US11.1).

Every read passes the server-side paywall first (402, FR-015, BR-001) and then looks only at
the requesting user's own latest run, so another user's report is never reachable (a user
with no report of their own gets 404, AC8.1.3).

The PDF is built on the first download, stored as a private MediaStore file and reused until
what it was built from changes: the template version, the front photo or any image slot
(AC8.5.2, AC8.5.3). A changed fingerprint rebuilds it and replaces the old file.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analysis.public import ResultView, latest_result_view
from app.measurement.public import FEATURE_KEYS
from app.media.public import MediaKind, MediaStore, StorageError
from app.payments.public import PaymentService, require_paid
from app.platform.clock import Clock
from app.platform.errors import NotFound, ReportNotReady
from app.report import repositories, template
from app.report.assembly import assemble
from app.report.home import assemble_home
from app.report.pdf import PdfImage, prepare_image, render_pdf
from app.report.schemas import HomeOut, ReportOut

logger = logging.getLogger("report")

PDF_CONTENT_TYPE = "application/pdf"


@dataclass(frozen=True)
class PdfFile:
    """The report PDF ready to send."""

    data: bytes
    cached: bool


def fingerprint(view: ResultView) -> str:
    """What the PDF is built from; any change makes the next download rebuild it."""
    parts = [template.TEMPLATE_VERSION, str(view.front_file_id), view.published_at.isoformat()]
    for slot in sorted(view.slots, key=lambda item: item.slot_key):
        parts.append(f"{slot.slot_key}:{slot.status}:{slot.media_file_id}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class ReportService:
    """Reads and renders the report.

    Args:
        payments: The paywall (``require_paid``).
        media: Private storage for the images and the cached PDF.
        clock: Time source.
    """

    def __init__(self, *, payments: PaymentService, media: MediaStore, clock: Clock) -> None:
        self.payments = payments
        self.media = media
        self.clock = clock

    def _view(self, session: Session, user_id: uuid.UUID) -> ResultView:
        require_paid(self.payments, session, user_id)
        view = latest_result_view(session, user_id)
        if view is None or view.user_id != user_id:
            raise ReportNotReady()
        return view

    def report(self, session: Session, user_id: uuid.UUID) -> ReportOut:
        """The published report (US8.1)."""
        return assemble(self._view(session, user_id))

    def home(self, session: Session, user_id: uuid.UUID) -> HomeOut:
        """The Home Overview data (US11.1)."""
        return assemble_home(self._view(session, user_id))

    # --- PDF ----------------------------------------------------------------------------------

    def pdf(self, session: Session, user_id: uuid.UUID) -> PdfFile:
        """The report PDF: the cached one when current, otherwise built now (US8.5)."""
        view = self._view(session, user_id)
        current = fingerprint(view)
        row = repositories.find_pdf(session, view.run_id)
        if row is not None and row.fingerprint == current:
            try:
                return PdfFile(self.media.get(session, row.media_file_id, user_id).data, True)
            except (NotFound, StorageError):
                logger.warning("cached report pdf missing", extra={"event": "report.pdf.missing"})
        data = self._render(session, user_id, view)
        self._store(session, user_id, view, current, data)
        return PdfFile(data, False)

    def _image(
        self, session: Session, user_id: uuid.UUID, file_id: uuid.UUID | None
    ) -> PdfImage | None:
        if file_id is None:
            return None
        try:
            return prepare_image(self.media.get(session, file_id, user_id).data)
        except (NotFound, StorageError):
            return None

    def _render(self, session: Session, user_id: uuid.UUID, view: ResultView) -> bytes:
        report = assemble(view)
        front = self._image(session, user_id, view.front_file_id)
        slots = {slot.slot_key: slot for slot in view.slots}
        afters: dict[str, PdfImage] = {}
        for key in FEATURE_KEYS:
            slot = slots.get(key)
            if slot is not None and slot.status == "ready":
                image = self._image(session, user_id, slot.media_file_id)
                if image is not None:
                    afters[key] = image
        data, _pages = render_pdf(report, front, afters)
        return data

    def _store(
        self, session: Session, user_id: uuid.UUID, view: ResultView, current: str, data: bytes
    ) -> None:
        ref = self.media.put(session, user_id, MediaKind.REPORT_PDF, data, PDF_CONTENT_TYPE)
        stale_key: str | None = None
        try:
            row = repositories.find_pdf(session, view.run_id, lock=True)
            if row is None:
                repositories.add_pdf(
                    session,
                    run_id=view.run_id,
                    user_id=user_id,
                    media_file_id=ref.file_id,
                    fingerprint=current,
                    now=self.clock.now(),
                )
            else:
                old_file = row.media_file_id
                row.media_file_id = ref.file_id
                row.fingerprint = current
                row.created_at = self.clock.now()
                session.flush()
                stale_key = self.media.retire(session, old_file)
            session.commit()
        except IntegrityError:
            # A concurrent first download stored its PDF first; ours is simply dropped.
            session.rollback()
            self.media.discard(ref)
            return
        except Exception:
            session.rollback()
            self.media.discard(ref)
            raise
        if stale_key is not None:
            self.media.purge([stale_key])
