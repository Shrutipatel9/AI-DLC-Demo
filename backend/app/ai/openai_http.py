"""Shared HTTP plumbing of the OpenAI adapters: timeouts and typed errors (AC1.12.2).

Only the HTTP status and the vendor's ``Retry-After`` hint leave this module. A request or
response body is never put in an error message or a log (NFR3.2).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.ai.errors import (
    AiBadOutputError,
    AiRateLimitError,
    AiRequestRejectedError,
    AiTimeoutError,
    AiUnavailableError,
)

logger = logging.getLogger("ai")

HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500
HTTP_CLIENT_ERROR = 400


def post(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    timeout_seconds: float,
    operation: str,
    json: dict[str, Any] | None = None,
    data: dict[str, str] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> dict[str, Any]:
    """POST and return the JSON body, or raise a typed ``AiError``.

    Args:
        client: The HTTP client (tests inject one with a mock transport).
        url: The full endpoint URL.
        headers: Request headers (including the bearer token, which is never logged).
        timeout_seconds: The call's timeout (connect, read, write and pool).
        operation: ``text`` or ``image``, for the log line.
        json: A JSON body.
        data: Form fields (multipart).
        files: Multipart files.

    Raises:
        AiTimeoutError: The vendor did not answer in time.
        AiUnavailableError: The vendor was unreachable or answered 5xx.
        AiRateLimitError: The vendor answered 429.
        AiRequestRejectedError: The vendor answered another 4xx.
        AiBadOutputError: The answer was not a JSON object.
    """
    try:
        response = client.post(
            url,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout_seconds,
        )
    except httpx.TimeoutException:
        logger.warning("vendor call timed out", extra={"event": "ai.timeout", "reason": operation})
        raise AiTimeoutError("The AI service did not answer in time.") from None
    except httpx.HTTPError:
        logger.warning("vendor unreachable", extra={"event": "ai.unreachable", "reason": operation})
        raise AiUnavailableError("The AI service could not be reached.") from None

    status = response.status_code
    if status == HTTP_TOO_MANY_REQUESTS:
        logger.warning("vendor rate limit", extra={"event": "ai.rate_limited", "reason": operation})
        raise AiRateLimitError(retry_after=_retry_after(response))
    if status >= HTTP_SERVER_ERROR:
        logger.warning(
            "vendor server error",
            extra={"event": "ai.unavailable", "reason": operation, "status": status},
        )
        raise AiUnavailableError(f"The AI service answered {status}.")
    if status >= HTTP_CLIENT_ERROR:
        logger.warning(
            "vendor rejected the request",
            extra={"event": "ai.rejected", "reason": operation, "status": status},
        )
        raise AiRequestRejectedError(f"The AI service refused the request ({status}).")
    try:
        body = response.json()
    except ValueError:
        raise AiBadOutputError("The AI service did not answer with JSON.") from None
    if not isinstance(body, dict):
        raise AiBadOutputError("The AI service answered with an unexpected shape.")
    return body


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None
