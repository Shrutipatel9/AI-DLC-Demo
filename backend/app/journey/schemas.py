"""Response model for ``GET /journey/next-step`` (contract C1 ``NextStep``, camelCase)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class NextStepOut(BaseModel):
    """The next step. ``flaggedAngles`` is additive to C1 [Decided by delivery team]."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    step: Literal[
        "consent",
        "questionnaire",
        "photos",
        "payment",
        "confirming_payment",
        "start_analysis",
        "progress",
        "home",
    ]
    flagged_angles: list[str]
