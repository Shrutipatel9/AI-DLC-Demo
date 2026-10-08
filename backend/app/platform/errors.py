"""Shared error format and error codes (contract C11, BR6.1, NFR3.3, NFR5.9).

Every non-2xx response has the body::

    {"error": {"code": "...", "message": "...", "details": [...], "requestId": "..."}}

The frontend branches only on ``code``. Messages are plain language and safe to show.
Stack traces go to logs only, never to a response.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.platform.request_id import get_request_id

logger = logging.getLogger("platform.errors")


class ErrorCode(StrEnum):
    """C11 error codes used so far (the full list grows with later units)."""

    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    SESSION_INVALID = "SESSION_INVALID"
    CSRF_CHECK_FAILED = "CSRF_CHECK_FAILED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    CODE_INVALID = "CODE_INVALID"
    CODE_EXPIRED = "CODE_EXPIRED"
    CODE_LOCKED = "CODE_LOCKED"
    CODE_RESEND_COOLDOWN = "CODE_RESEND_COOLDOWN"
    RESET_TOKEN_INVALID = "RESET_TOKEN_INVALID"  # noqa: S105  (an error code, not a secret)
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    DISCLAIMER_REQUIRED = "DISCLAIMER_REQUIRED"
    QUESTIONNAIRE_NOT_SUBMITTED = "QUESTIONNAIRE_NOT_SUBMITTED"
    #: [Decided by delivery team] U3 plan: C1 documents a 409 for changing a submitted
    #: questionnaire but C11 names no code for it.
    QUESTIONNAIRE_ALREADY_SUBMITTED = "QUESTIONNAIRE_ALREADY_SUBMITTED"
    PHOTO_REJECTED = "PHOTO_REJECTED"
    PHOTO_TOO_LARGE = "PHOTO_TOO_LARGE"
    PHOTO_UNSUPPORTED_TYPE = "PHOTO_UNSUPPORTED_TYPE"
    PHOTO_SET_INCOMPLETE = "PHOTO_SET_INCOMPLETE"
    PHOTO_IDENTITY_MISMATCH = "PHOTO_IDENTITY_MISMATCH"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    ALREADY_PAID = "ALREADY_PAID"
    ANALYSIS_ALREADY_COMPLETE = "ANALYSIS_ALREADY_COMPLETE"
    RERUN_NOT_AVAILABLE = "RERUN_NOT_AVAILABLE"
    #: [Decided by delivery team] U7: the image cannot be retried (not failed, or 3 retries used).
    IMAGE_RETRY_NOT_AVAILABLE = "IMAGE_RETRY_NOT_AVAILABLE"
    #: Contract C11: the paid user has no published report yet.
    REPORT_NOT_READY = "REPORT_NOT_READY"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"  # [Decided by delivery team] plan decision D3
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


Detail = dict[str, Any]


class AppError(Exception):
    """Base class for errors that map to a C11 response.

    Args:
        message: Plain-language text safe to show a user. Defaults per subclass.
        details: Optional detail items (``field``, ``reason``, ``attemptsLeft`` ...).
        retry_after: Seconds for the ``Retry-After`` header, when relevant.
    """

    status_code: int = 500
    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    default_message: str = "Something went wrong on our side. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Sequence[Detail] | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details: list[Detail] = list(details or [])
        self.retry_after = retry_after
        super().__init__(self.message)

    def headers(self) -> dict[str, str]:
        """Extra response headers (``Retry-After`` when set)."""
        if self.retry_after is None:
            return {}
        return {"Retry-After": str(max(1, int(self.retry_after)))}


class ValidationFailed(AppError):  # noqa: N818  (named after the C11 code)
    """422: input shape or rule failed."""

    status_code = 422
    code = ErrorCode.VALIDATION_FAILED
    default_message = "Some of the information you entered isn't valid."


class NotAuthenticated(AppError):  # noqa: N818  (named after the C11 code)
    """401: missing, expired or invalid access token."""

    status_code = 401
    code = ErrorCode.NOT_AUTHENTICATED
    default_message = "Please sign in to continue."


class SessionInvalid(AppError):  # noqa: N818  (named after the C11 code)
    """401: the refresh cookie is missing, expired, revoked or reused (U2 BR2.2-BR2.4).

    Carries one detail item whose ``reason`` is ``EXPIRED``, ``REUSE_DETECTED``,
    ``REVOKED`` or ``INVALID``. The frontend clears its auth state on this code.
    """

    status_code = 401
    code = ErrorCode.SESSION_INVALID
    default_message = "Your session has ended. Please log in again."

    def __init__(self, reason: str) -> None:
        super().__init__(details=[{"reason": reason}])
        self.reason = reason


class CsrfCheckFailed(AppError):  # noqa: N818  (named after the C11 code)
    """403: ``X-Requested-With`` or the Origin/Referer allow-list check failed (BR2.5)."""

    status_code = 403
    code = ErrorCode.CSRF_CHECK_FAILED
    default_message = "This request was blocked for your security."


class ResetTokenInvalid(AppError):  # noqa: N818  (named after the C11 code)
    """401: the reset token is unknown, used or expired (U2 BR4.4)."""

    status_code = 401
    code = ErrorCode.RESET_TOKEN_INVALID
    default_message = "This reset link has expired. Please start again."


class InvalidCredentials(AppError):  # noqa: N818  (named after the C11 code)
    """401: wrong email or password (never says which)."""

    status_code = 401
    code = ErrorCode.INVALID_CREDENTIALS
    default_message = "Email or password is incorrect."


class EmailAlreadyRegistered(AppError):  # noqa: N818  (named after the C11 code)
    """409: sign-up with an email that belongs to a verified account."""

    status_code = 409
    code = ErrorCode.EMAIL_ALREADY_REGISTERED
    default_message = "An account with this email already exists. Sign in instead?"


class CodeInvalid(AppError):  # noqa: N818  (named after the C11 code)
    """401: wrong, used, superseded or unknown code. Carries ``attemptsLeft`` when known."""

    status_code = 401
    code = ErrorCode.CODE_INVALID
    default_message = "That code isn't right."

    def __init__(self, attempts_left: int | None = None) -> None:
        details: list[Detail] = []
        if attempts_left is not None:
            details.append({"reason": "CODE_INVALID", "attemptsLeft": attempts_left})
        super().__init__(details=details)


class CodeExpired(AppError):  # noqa: N818  (named after the C11 code)
    """401: the code is 10 minutes old or older."""

    status_code = 401
    code = ErrorCode.CODE_EXPIRED
    default_message = "This code has expired."


class CodeLocked(AppError):  # noqa: N818  (named after the C11 code)
    """429: five wrong codes; locked until the lock ends (Retry-After)."""

    status_code = 429
    code = ErrorCode.CODE_LOCKED
    default_message = "Too many tries. Please wait before trying again."


class CodeResendCooldown(AppError):  # noqa: N818  (named after the C11 code)
    """429: a new code was requested within 60 seconds of the previous one."""

    status_code = 429
    code = ErrorCode.CODE_RESEND_COOLDOWN
    default_message = "Please wait a moment before asking for a new code."


class ConsentRequired(AppError):  # noqa: N818  (named after the C11 code)
    """403: a questionnaire action before consent to the current consent text (US4.1).

    The same code with status 409 and reason ``CONSENT_VERSION_CHANGED`` answers a consent
    given to an out-of-date text version (contract C1 ``POST /onboarding/consent``).
    """

    status_code = 403
    code = ErrorCode.CONSENT_REQUIRED
    default_message = "Please read and agree to the consent before continuing."


class ConsentVersionChanged(ConsentRequired):
    """409: the consent text changed since the page was loaded; show the new text."""

    status_code = 409
    default_message = "The consent text has changed. Please read it again."

    def __init__(self) -> None:
        super().__init__(details=[{"reason": "CONSENT_VERSION_CHANGED"}])


class DisclaimerRequired(AppError):  # noqa: N818  (named after the C11 code)
    """422: submitting the questionnaire without confirming the disclaimer (BR-003)."""

    status_code = 422
    code = ErrorCode.DISCLAIMER_REQUIRED
    default_message = "Please confirm the statement to submit your answers."


class QuestionnaireNotSubmitted(AppError):  # noqa: N818  (named after the C11 code)
    """409: a later step needs a submitted questionnaire."""

    status_code = 409
    code = ErrorCode.QUESTIONNAIRE_NOT_SUBMITTED
    default_message = "Please finish the questionnaire first."


class QuestionnaireAlreadySubmitted(AppError):  # noqa: N818  (named after the code)
    """409: answers cannot change after the questionnaire was submitted."""

    status_code = 409
    code = ErrorCode.QUESTIONNAIRE_ALREADY_SUBMITTED
    default_message = "Your questionnaire is already submitted."


class PhotoRejected(AppError):  # noqa: N818  (named after the C11 code)
    """422: a per-photo check failed (BR-005). ``details`` has one ``{angle, reason}`` each."""

    status_code = 422
    code = ErrorCode.PHOTO_REJECTED
    default_message = "This photo can't be used. Please check the tips and try again."

    def __init__(self, angle: str, reasons: Sequence[str]) -> None:
        super().__init__(details=[{"angle": angle, "reason": reason} for reason in reasons])
        self.angle = angle
        self.reasons = list(reasons)


class PhotoTooLarge(AppError):  # noqa: N818  (named after the C11 code)
    """413: the upload is over the configured limit (10 MB by default; AC5.2.3)."""

    status_code = 413
    code = ErrorCode.PHOTO_TOO_LARGE
    default_message = "This photo is too large. Please choose a smaller photo."


class PhotoUnsupportedType(AppError):  # noqa: N818  (named after the C11 code)
    """415: the file is not a JPEG, PNG or HEIC image (AC5.2.3)."""

    status_code = 415
    code = ErrorCode.PHOTO_UNSUPPORTED_TYPE
    default_message = "Please upload a JPEG, PNG or HEIC photo."


class PhotoSetIncomplete(AppError):  # noqa: N818  (named after the C11 code)
    """409: not every required angle has an accepted photo (C4 ``snapshot_for_run``)."""

    status_code = 409
    code = ErrorCode.PHOTO_SET_INCOMPLETE
    default_message = "Please add a photo for every angle first."


class PhotoIdentityMismatch(AppError):  # noqa: N818  (named after the C11 code)
    """409: the same-person check failed; ``details`` names each flagged angle (BR-005)."""

    status_code = 409
    code = ErrorCode.PHOTO_IDENTITY_MISMATCH
    default_message = (
        "Your photos don't appear to show the same person. Please retake the flagged photo."
    )

    def __init__(self, mismatched_angles: Sequence[str]) -> None:
        super().__init__(
            details=[{"angle": angle, "reason": "IDENTITY_MISMATCH"} for angle in mismatched_angles]
        )
        self.mismatched_angles = list(mismatched_angles)


class PaymentRequired(AppError):  # noqa: N818  (named after the C11 code)
    """402: no successful payment yet (FR-015, BR-001; checked before the photo set, AC6.4.2)."""

    status_code = 402
    code = ErrorCode.PAYMENT_REQUIRED
    default_message = "Please complete your payment first."


class AlreadyPaid(AppError):  # noqa: N818  (named after the C11 code)
    """409: checkout after a successful payment (one payment per report, FR7.2)."""

    status_code = 409
    code = ErrorCode.ALREADY_PAID
    default_message = "You've already paid for your report."


class AnalysisAlreadyComplete(AppError):  # noqa: N818  (named after the C11 code)
    """409: start after a completed run (one analysis per paid report, NFR10, AC7.1.4)."""

    status_code = 409
    code = ErrorCode.ANALYSIS_ALREADY_COMPLETE
    default_message = "Your analysis is already complete."


class RerunNotAvailable(AppError):  # noqa: N818  (named after the C11 code)
    """409: the free re-run is used up, or the run has not failed (US7.11)."""

    status_code = 409
    code = ErrorCode.RERUN_NOT_AVAILABLE
    default_message = "A re-run isn't available for this analysis."


class ImageRetryNotAvailable(AppError):  # noqa: N818  (named after the code)
    """409: the image is not marked "not available yet", or its manual retries are used up."""

    status_code = 409
    code = ErrorCode.IMAGE_RETRY_NOT_AVAILABLE
    default_message = "This image can't be retried right now."


class ReportNotReady(AppError):  # noqa: N818  (named after the C11 code)
    """404: the user has no published report yet (contract C11 ``REPORT_NOT_READY``)."""

    status_code = 404
    code = ErrorCode.REPORT_NOT_READY
    default_message = "Your report isn't ready yet."


class WebhookRejected(AppError):  # noqa: N818  (named like the other C11 errors)
    """400: a webhook whose signature fails against the raw body, or an unreadable body.

    Nothing changes (contract C2, AC6.3.3). ``details`` carries ``SIGNATURE_INVALID`` or
    ``PAYLOAD_UNREADABLE``; the provider retries any non-2xx answer.
    """

    status_code = 400
    code = ErrorCode.VALIDATION_FAILED
    default_message = "The webhook could not be verified."

    def __init__(self, reason: str) -> None:
        super().__init__(details=[{"field": "body", "reason": reason}])
        self.reason = reason


class NotFound(AppError):  # noqa: N818  (named after the C11 code)
    """404: missing, or owned by another user (never 403, to hide existence)."""

    status_code = 404
    code = ErrorCode.NOT_FOUND
    default_message = "We couldn't find that."


class RateLimited(AppError):  # noqa: N818  (named after the C11 code)
    """429: too many requests from this address (per-IP limiter, NFR2.9)."""

    status_code = 429
    code = ErrorCode.RATE_LIMITED
    default_message = "Too many requests. Please wait a moment and try again."


class UpstreamUnavailable(AppError):  # noqa: N818  (named after the C11 code)
    """502 (or 503 when we refuse to call out): an outside service failed after retries."""

    status_code = 502
    code = ErrorCode.UPSTREAM_UNAVAILABLE
    default_message = "We couldn't send the email. Please try again."

    def __init__(self, message: str | None = None, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class UpstreamTimeout(AppError):  # noqa: N818  (named after the C11 code)
    """504: an outside service did not answer in time."""

    status_code = 504
    code = ErrorCode.UPSTREAM_TIMEOUT
    default_message = "We couldn't send the email in time. Please try again."


def error_body(
    code: ErrorCode | str,
    message: str,
    details: Sequence[Mapping[str, Any]] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the C11 envelope."""
    return {
        "error": {
            "code": str(code),
            "message": message,
            "details": [dict(item) for item in details or []],
            "requestId": request_id or get_request_id(),
        }
    }


def error_response(error: AppError) -> JSONResponse:
    """Render an :class:`AppError` as a JSON response."""
    return JSONResponse(
        status_code=error.status_code,
        content=error_body(error.code, error.message, error.details),
        headers=error.headers(),
    )


def internal_error_response() -> JSONResponse:
    """The generic 500 body (no internal detail)."""
    return JSONResponse(
        status_code=500,
        content=error_body(ErrorCode.INTERNAL_ERROR, AppError.default_message),
    )


_HTTP_STATUS_TO_CODE: dict[int, tuple[ErrorCode, str]] = {
    401: (ErrorCode.NOT_AUTHENTICATED, NotAuthenticated.default_message),
    403: (ErrorCode.NOT_FOUND, NotFound.default_message),
    404: (ErrorCode.NOT_FOUND, NotFound.default_message),
    405: (ErrorCode.NOT_FOUND, "This action isn't available here."),
    413: (ErrorCode.VALIDATION_FAILED, ValidationFailed.default_message),
    415: (ErrorCode.VALIDATION_FAILED, ValidationFailed.default_message),
    422: (ErrorCode.VALIDATION_FAILED, ValidationFailed.default_message),
    429: (ErrorCode.RATE_LIMITED, RateLimited.default_message),
}


def _validation_details(exc: RequestValidationError) -> list[Detail]:
    details: list[Detail] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query")]
        reason = str(error.get("type", "invalid")).upper()
        item: Detail = {"field": ".".join(location) or "body", "reason": reason}
        context = error.get("ctx") or {}
        if "reason" in context and isinstance(context["reason"], str):
            item["reason"] = context["reason"]
        details.append(item)
    return details


async def _app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101  (registered for AppError only)
    return error_response(exc)


async def _validation_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    return JSONResponse(
        status_code=422,
        content=error_body(
            ErrorCode.VALIDATION_FAILED, ValidationFailed.default_message, _validation_details(exc)
        ),
    )


async def _http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code, message = _HTTP_STATUS_TO_CODE.get(
        exc.status_code, (ErrorCode.INTERNAL_ERROR, AppError.default_message)
    )
    headers = dict(exc.headers or {})
    return JSONResponse(
        status_code=exc.status_code, content=error_body(code, message), headers=headers
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Map typed errors, framework validation errors and HTTP errors to C11 bodies.

    Unexpected exceptions are handled by ``CatchAllMiddleware`` (inside CORS) so the
    500 response still carries CORS and security headers.
    """
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)


# --- OpenAPI description of the envelope (contract C11; plan decision D3) ------------------


class ErrorDetail(BaseModel):
    """One detail item. ``attemptsLeft`` is sent with ``CODE_INVALID`` (D3)."""

    model_config = ConfigDict(extra="allow")

    field: str | None = None
    reason: str | None = None
    #: The photo angle, for photo errors (C11).
    angle: str | None = None
    attempts_left: int | None = Field(default=None, alias="attemptsLeft")


class ErrorObject(BaseModel):
    """The ``error`` object."""

    code: ErrorCode
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str = Field(alias="requestId")


class ErrorResponse(BaseModel):
    """Every non-2xx body (contract C11)."""

    error: ErrorObject


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """``responses=`` entries documenting the C11 envelope for the given statuses."""
    return {
        status: {"model": ErrorResponse, "description": "Error (contract C11)"}
        for status in statuses
    }
