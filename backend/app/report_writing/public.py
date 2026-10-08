"""The ReportWriting module's public interface. Other modules import only this.

- ``build_report_writing``: the service from settings and a ``TextModel``.
- ``fake_report``: the text fake's default responder (composition roots pass it to
  ``build_text_model`` when the provider is the fake).
- ``classify``: the keyword tier rules (also used when a stored tier is missing or invalid).
- ``AnswerForAi``: a non-medical answer with its question text.
- ``ReportWritingFailed``: no attempt produced valid text.
"""

from __future__ import annotations

import time

from app.ai.public import TextModel
from app.platform.settings import Settings
from app.report_writing.fake_responder import fake_report
from app.report_writing.request import REASSURANCE_INSTRUCTION, AnswerForAi
from app.report_writing.service import ReportWritingFailed, ReportWritingService, Sleeper
from app.report_writing.tiers import AT_HOME, IN_CLINIC, OVER_THE_COUNTER, TIERS, classify

__all__ = [
    "AT_HOME",
    "IN_CLINIC",
    "OVER_THE_COUNTER",
    "REASSURANCE_INSTRUCTION",
    "TIERS",
    "AnswerForAi",
    "ReportWritingFailed",
    "ReportWritingService",
    "build_report_writing",
    "classify",
    "fake_report",
]


def build_report_writing(
    settings: Settings, *, text_model: TextModel, sleep: Sleeper = time.sleep
) -> ReportWritingService:
    """Create the report-writing service from settings."""
    return ReportWritingService(
        text_model=text_model,
        max_attempts=settings.ai_text_max_attempts,
        backoff_seconds=settings.ai_retry_backoff_seconds,
        decimals=settings.report_value_decimals,
        sleep=sleep,
    )
