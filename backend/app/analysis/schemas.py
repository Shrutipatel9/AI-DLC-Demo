"""Response models for ``/analysis/*`` (contract C1 ``AnalysisRun``; camelCase JSON).

Additive to C1 [Decided by delivery team]: ``expectedWaitMinutes`` (the configured wait shown
on the progress screen, AC7.2.2) and ``contactSupport`` (the free re-run failed too, AC7.11.3).
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.analysis.domain import RunView


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StepOut(CamelModel):
    """One named step and its state in text."""

    key: Literal["measuring", "writing", "generating_images", "assembling"]
    state: Literal["done", "current", "waiting", "failed"]


class AnalysisRunOut(CamelModel):
    """``AnalysisRun``: the progress screen's whole picture."""

    run_id: uuid.UUID
    status: Literal["running", "completed", "failed"]
    steps: list[StepOut]
    rerun_available: bool
    failure_message: str | None = None
    contact_support: bool
    expected_wait_minutes: int


def to_out(view: RunView) -> AnalysisRunOut:
    """The wire form of a :class:`RunView`."""
    return AnalysisRunOut(
        run_id=view.run_id,
        status=view.status,
        steps=[StepOut(key=key, state=state) for key, state in view.steps],
        rerun_available=view.rerun_available,
        failure_message=view.failure_message,
        contact_support=view.contact_support,
        expected_wait_minutes=view.expected_wait_minutes,
    )
