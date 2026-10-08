"""The pure next-step table (AC11.8.1) without a database."""

from __future__ import annotations

import pytest

from app.journey.rule import NextStep, Progress, next_step

READY = {"consented": True, "submitted": True, "photos_complete": True, "photos_consistent": True}


@pytest.mark.parametrize(
    ("progress", "expected"),
    [
        (Progress(False, False, False, False), "consent"),
        (Progress(True, False, False, False), "questionnaire"),
        (Progress(True, True, False, False), "photos"),
        (Progress(True, True, True, False, ("right_3q",)), "photos"),
        (Progress(**READY), "payment"),
        (Progress(**READY, payment="pending"), "confirming_payment"),
        (Progress(**READY, payment="paid"), "start_analysis"),
        (Progress(**READY, payment="paid", run_status="running"), "progress"),
        (Progress(**READY, payment="paid", run_status="failed"), "progress"),
        (Progress(**READY, payment="paid", run_status="completed"), "progress"),
        (Progress(**READY, payment="paid", run_status="completed", report_exists=True), "home"),
    ],
)
def test_each_row_of_the_table_returns_exactly_one_step(progress: Progress, expected: str) -> None:
    assert next_step(progress).step == expected


def test_flagged_angles_travel_only_with_the_photos_step() -> None:
    flagged = next_step(Progress(True, True, True, False, ("right_3q",)))
    assert flagged == NextStep("photos", ("right_3q",))
    assert next_step(Progress(**READY)).flagged_angles == ()
