"""ReportWriting: ask the text model for the report text and keep only valid output (US7.9).

The call is retried up to ``AI_TEXT_MAX_ATTEMPTS`` times. A vendor error (a timeout, a rate
limit, an unavailable service) and output that fails validation each use one attempt, with a
pause between them (a rate limit uses the vendor's own hint when it gave one). After the last
attempt the step fails with a plain-language reason (AC7.9.2). The text is only returned once
every feature has passed validation, so nothing half-valid is ever stored.

Logs carry the attempt number and the kind of failure, never the text, the answers or the
vendor's message.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.ai.public import AiError, AiRateLimitError, ImageInput, TextModel
from app.report_writing import schema
from app.report_writing.request import AnswerForAi, build_request
from app.report_writing.validation import InvalidReportText, validate_report_text

logger = logging.getLogger("report_writing")

Sleeper = Callable[[float], None]

FAILURE_REASON = "The report text could not be written."


class ReportWritingFailed(Exception):  # noqa: N818  (reads better at the raise site)
    """Every attempt failed. ``reason`` is plain language and safe to store."""

    def __init__(self, reason: str = FAILURE_REASON) -> None:
        super().__init__(reason)
        self.reason = reason


class ReportWritingService:
    """Writes the report text.

    Args:
        text_model: The configured ``TextModel`` (OpenAI or the fake).
        max_attempts: ``AI_TEXT_MAX_ATTEMPTS``.
        backoff_seconds: Pause between attempts (``AI_RETRY_BACKOFF_SECONDS``).
        decimals: ``REPORT_VALUE_DECIMALS``.
        sleep: Sleep function (tests inject a virtual one).
    """

    def __init__(
        self,
        *,
        text_model: TextModel,
        max_attempts: int,
        backoff_seconds: float,
        decimals: int,
        sleep: Sleeper = time.sleep,
    ) -> None:
        self.text_model = text_model
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.decimals = decimals
        self._sleep = sleep

    def write(
        self,
        *,
        answers: Sequence[AnswerForAi],
        measurements: Mapping[str, Any],
        photos: Sequence[ImageInput],
        reassure: bool,
    ) -> dict[str, Any]:
        """The validated, tiered text for all 11 features.

        Raises:
            ReportWritingFailed: When no attempt produced valid text.
        """
        messages, images = build_request(
            answers=answers,
            measurements=measurements,
            photos=photos,
            reassure=reassure,
            decimals=self.decimals,
        )
        for attempt in range(1, self.max_attempts + 1):
            pause = self.backoff_seconds
            try:
                output = self.text_model.generate_structured(
                    messages, images, schema.output_schema()
                )
                return validate_report_text(output, measurements["features"], self.decimals)
            except InvalidReportText as invalid:
                logger.warning(
                    "report text invalid",
                    extra={
                        "event": "report.invalid",
                        "attempt": attempt,
                        "count": len(invalid.problems),
                    },
                )
            except AiError as error:
                logger.warning(
                    "report text vendor error",
                    extra={
                        "event": "report.vendor_error",
                        "attempt": attempt,
                        "errorClass": type(error).__name__,
                    },
                )
                if isinstance(error, AiRateLimitError) and error.retry_after is not None:
                    pause = max(pause, error.retry_after)
            if attempt < self.max_attempts and pause > 0:
                self._sleep(pause)
        raise ReportWritingFailed()
