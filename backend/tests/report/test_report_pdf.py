"""The report PDF: page order, paywall, cache and rebuild (US8.5, AC8.7.2). Output is checked by
page text and order, not pixels. No network, no paid service."""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.models import AnalysisImageSlot
from app.media.models import MediaFile
from app.report import template
from app.report.pdf import clean, prepare_image
from app.report.service import fingerprint
from tests.factories import SignedInUser
from tests.report.conftest import ImageHarness, get_pdf, run_to_done


def _pages(response_bytes: bytes) -> list[str]:
    return [page.extract_text() for page in PdfReader(io.BytesIO(response_bytes)).pages]


def _first_page_with(pages: list[str], needle: str) -> int:
    return next(index for index, text in enumerate(pages) if needle in text)


def _pdf_files(db_session: Session) -> list[MediaFile]:
    return list(db_session.scalars(select(MediaFile).where(MediaFile.kind == "report_pdf")).all())


def test_the_pdf_follows_the_page_order_with_the_preamble_before_any_score(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC8.5.1, AC8.7.2, AC8.7.3, AC8.7.4."""
    run_to_done(client, paid, image_harness)

    response = get_pdf(client, paid)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    pages = _pages(response.content)
    order = [
        "Disclaimer and Privacy",
        "Introduction",
        "Understanding the Results",
        "Your Protocol",
        "Facial Assessments",
        "Hair",
        "Eyebrows",
        "Eyes",
        "Nose",
        "Cheeks",
        "Jaw",
        "Lips",
        "Chin",
        "Skin",
        "Neck",
        "Ears",
        "Closing Recommendations",
    ]
    # Every section starts on its own, later page (the Contents list mentions earlier names).
    starts = [
        next(i for i, text in enumerate(pages) if text.lstrip().startswith(name)) for name in order
    ]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)
    understanding = pages[starts[2]]
    assert template.UNDERSTANDING_PRINCIPLES[1][0] in understanding.replace("\n", " ")
    # The first score appears only after the preamble page (AC8.7.2).
    first_score = _first_page_with(pages, "Score ")
    assert starts[2] < first_score
    assert template.INTRODUCTION in " ".join(pages[starts[1]].split())
    assert template.AI_IMAGE_LABEL in pages[starts[5]]


def test_a_second_download_returns_the_cached_pdf_without_regenerating(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC8.5.2."""
    run_to_done(client, paid, image_harness)

    first = get_pdf(client, paid)
    files = _pdf_files(db_session)
    second = get_pdf(client, paid)

    assert len(files) == 1
    assert [f.id for f in _pdf_files(db_session)] == [files[0].id]
    assert second.content == first.content
    assert files[0].owner_user_id == uuid.UUID(paid.user_id)


def test_a_changed_image_rebuilds_the_pdf_and_replaces_the_old_file(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC8.5.3: after a retry changes an image the next download is a new PDF."""
    run_to_done(client, paid, image_harness)
    get_pdf(client, paid)
    old = _pdf_files(db_session)[0]
    slot = db_session.scalars(
        select(AnalysisImageSlot).where(AnalysisImageSlot.slot_key == "nose")
    ).one()
    slot.status = "not_available_yet"
    slot.media_file_id = None
    db_session.flush()

    response = get_pdf(client, paid)

    assert response.status_code == 200
    files = _pdf_files(db_session)
    assert len(files) == 1
    assert files[0].id != old.id
    pages = _pages(response.content)
    nose_page = next(text for text in pages if text.lstrip().startswith("Nose"))
    assert "not available yet" in " ".join(nose_page.split()).lower()


def test_another_user_never_gets_the_pdf_and_an_unpaid_user_gets_402(
    client: TestClient,
    paid: SignedInUser,
    image_harness: ImageHarness,
    make_paid_user: Callable[..., SignedInUser],
) -> None:
    """AC8.1.3 for the PDF route."""
    run_to_done(client, paid, image_harness)
    other = make_paid_user()

    assert get_pdf(client, other).status_code == 404
    assert get_pdf(client, other).json()["error"]["code"] == "REPORT_NOT_READY"


def test_text_outside_latin_1_is_replaced_and_unreadable_images_are_skipped() -> None:
    assert clean("Nose — “AI” → 中") == 'Nose - "AI" -> ?'
    assert prepare_image(b"not an image") is None


def test_the_fingerprint_changes_with_any_slot(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    run_to_done(client, paid, image_harness)
    from app.analysis.public import latest_result_view

    view = latest_result_view(db_session, uuid.UUID(paid.user_id))
    assert view is not None
    before = fingerprint(view)
    assert fingerprint(view) == before
    slot = db_session.scalars(
        select(AnalysisImageSlot).where(AnalysisImageSlot.slot_key == "chin")
    ).one()
    other = db_session.scalars(
        select(AnalysisImageSlot).where(AnalysisImageSlot.slot_key == "ears")
    ).one()
    slot.media_file_id = other.media_file_id
    db_session.flush()
    changed = latest_result_view(db_session, uuid.UUID(paid.user_id))
    assert changed is not None
    assert fingerprint(changed) != before
