"""The next-step table of AC11.8.1 as a pure function (no I/O, no state)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Step = Literal[
    "consent",
    "questionnaire",
    "photos",
    "payment",
    "confirming_payment",
    "start_analysis",
    "progress",
    "home",
]
PaymentState = Literal["none", "pending", "paid"]
RunStatus = Literal["running", "completed", "failed"]


@dataclass(frozen=True)
class Progress:
    """Everything the rule needs, read fresh from the owning modules on every call."""

    consented: bool
    submitted: bool
    photos_complete: bool
    photos_consistent: bool
    flagged_angles: tuple[str, ...] = field(default=())
    payment: PaymentState = "none"
    run_status: RunStatus | None = None
    report_exists: bool = False


@dataclass(frozen=True)
class NextStep:
    """The one step to show, plus the flagged photo angles when it is ``photos``."""

    step: Step
    flagged_angles: tuple[str, ...] = field(default=())


def next_step(progress: Progress) -> NextStep:
    """Return exactly one next step, following the order of AC11.8.1.

    A failed run keeps the user on ``progress``: the re-run and support message live there
    ([Decided by delivery team]). A finished run with no stored report is also ``progress``.
    """
    if not progress.consented:
        return NextStep("consent")
    if not progress.submitted:
        return NextStep("questionnaire")
    if not (progress.photos_complete and progress.photos_consistent):
        return NextStep("photos", progress.flagged_angles)
    if progress.report_exists:
        return NextStep("home")
    if progress.payment == "none":
        return NextStep("payment")
    if progress.payment == "pending":
        return NextStep("confirming_payment")
    if progress.run_status is None:
        return NextStep("start_analysis")
    return NextStep("progress")
