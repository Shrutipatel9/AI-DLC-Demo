"""Names, messages and the run view shared by the API service and the worker pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final, Literal

#: The named steps, in order (C7; US7.2, US7.6).
STEP_MEASURING: Final = "measuring"
STEP_WRITING: Final = "writing"
STEP_GENERATING_IMAGES: Final = "generating_images"
STEP_ASSEMBLING: Final = "assembling"
STEP_KEYS: Final = (STEP_MEASURING, STEP_WRITING, STEP_GENERATING_IMAGES, STEP_ASSEMBLING)

#: The kind of job that runs an analysis.
JOB_KIND: Final = "analysis.run"

FRONT_ANGLE: Final = "front"

#: Plain-language failure texts (AC7.11.1, AC7.11.3). Never a raw error.
FAILURE_MESSAGE: Final = (
    "Something went wrong on our side while preparing your report. "
    "Your payment still covers this report, and you can try again for free."
)
FAILURE_MESSAGE_FINAL: Final = (
    "Something went wrong on our side again. Your payment still covers this report. "
    "Please contact support and we will sort it out."
)

StepState = Literal["done", "current", "waiting", "failed"]


@dataclass(frozen=True)
class RunView:
    """The run as the progress screen needs it (contract ``AnalysisRun``)."""

    run_id: uuid.UUID
    status: Literal["running", "completed", "failed"]
    steps: tuple[tuple[str, StepState], ...]
    rerun_available: bool
    failure_message: str | None
    contact_support: bool
    expected_wait_minutes: int
