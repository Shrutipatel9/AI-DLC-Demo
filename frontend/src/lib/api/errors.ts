// Typed API errors (contract C11). The UI branches only on `code`, never on `message`.
import type { components } from "./types.gen";

export type ErrorCode = components["schemas"]["ErrorCode"];
export type ErrorDetail = components["schemas"]["ErrorDetail"];

/** Client-side codes for failures that never reached the server. */
export type ClientErrorCode = "NETWORK_ERROR" | "TIMEOUT";

const KNOWN_CODES: ReadonlySet<string> = new Set<ErrorCode>([
  "VALIDATION_FAILED",
  "NOT_AUTHENTICATED",
  "SESSION_INVALID",
  "CSRF_CHECK_FAILED",
  "INVALID_CREDENTIALS",
  "EMAIL_ALREADY_REGISTERED",
  "CODE_INVALID",
  "CODE_EXPIRED",
  "CODE_LOCKED",
  "CODE_RESEND_COOLDOWN",
  "RESET_TOKEN_INVALID",
  "CONSENT_REQUIRED",
  "DISCLAIMER_REQUIRED",
  "QUESTIONNAIRE_NOT_SUBMITTED",
  "QUESTIONNAIRE_ALREADY_SUBMITTED",
  "PHOTO_REJECTED",
  "PHOTO_TOO_LARGE",
  "PHOTO_UNSUPPORTED_TYPE",
  "PHOTO_SET_INCOMPLETE",
  "PHOTO_IDENTITY_MISMATCH",
  "PAYMENT_REQUIRED",
  "ALREADY_PAID",
  "ANALYSIS_ALREADY_COMPLETE",
  "RERUN_NOT_AVAILABLE",
  "REPORT_NOT_READY",
  "NOT_FOUND",
  "RATE_LIMITED",
  "UPSTREAM_UNAVAILABLE",
  "UPSTREAM_TIMEOUT",
  "INTERNAL_ERROR",
]);

/** An error from the API client, carrying the C11 code, details and request id. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode | ClientErrorCode;
  readonly details: ErrorDetail[];
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(options: {
    status: number;
    code: ErrorCode | ClientErrorCode;
    message: string;
    details?: ErrorDetail[];
    requestId?: string | null;
    retryAfterSeconds?: number | null;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? [];
    this.requestId = options.requestId ?? null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
  }

  /** The `attemptsLeft` value sent with CODE_INVALID, when present (plan decision D3). */
  get attemptsLeft(): number | null {
    const item = this.details.find((detail) => typeof detail.attemptsLeft === "number");
    return item?.attemptsLeft ?? null;
  }

  /** The `reason` codes of the details for one photo angle (PHOTO_REJECTED, U4). */
  reasonsFor(angle: string): string[] {
    return this.details
      .filter((detail) => detail.angle === angle && typeof detail.reason === "string")
      .map((detail) => detail.reason as string);
  }

  /** Field-level errors (`field` -> `reason`) from a VALIDATION_FAILED response. */
  get fieldErrors(): Record<string, string> {
    const fields: Record<string, string> = {};
    for (const detail of this.details) {
      if (detail.field && detail.reason) {
        fields[detail.field] = detail.reason;
      }
    }
    return fields;
  }
}

/** Unknown codes are treated as INTERNAL_ERROR (contract ownership rule 3). */
export function normaliseCode(code: unknown): ErrorCode {
  return typeof code === "string" && KNOWN_CODES.has(code) ? (code as ErrorCode) : "INTERNAL_ERROR";
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}
