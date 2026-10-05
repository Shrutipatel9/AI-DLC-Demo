// The single API client (FE-004, BR5.2, AC1.9.2). Every frontend HTTP call goes through it.
//
// - Adds `Authorization: Bearer <token>` when the auth store has a token. The client never
//   imports the store; the store registers a token provider (layering: store -> client).
// - Always sends `credentials: "include"` (so U2's refresh cookie flow works unchanged)
//   and `X-Requested-With: XMLHttpRequest` (contract C1 §3, plan decision D2).
// - Aborts after 30 s (contract §6); photo uploads pass a longer `timeoutMs`.
// - A `FormData` body is sent as multipart (the browser sets the boundary); any other body is
//   JSON. `apiBlob` reads a binary response (private photos, U4) as a `Blob`.
// - Throws `ApiError` with the C11 `code`, `details` and `requestId` (NFR5.11).
// - 401 with code NOT_AUTHENTICATED (and only that code) awaits the shared refresh that the
//   auth store registers, then retries the request once (FE-005, FE-006; BR6.3, BR6.4). A
//   retried request that gets 401 again is not retried. `apiRaw` bypasses this handler; the
//   refresh and logout calls use it, so a refresh 401 can never start another refresh.
import { ApiError, normaliseCode, type ErrorDetail } from "./errors";

export const DEFAULT_TIMEOUT_MS = 30_000;

type TokenProvider = () => string | null;

let apiOrigin = "";
let tokenProvider: TokenProvider = () => null;

/** Set the API origin (read at request time from the server, see ApiConfigProvider). */
export function configureApiOrigin(origin: string): void {
  apiOrigin = origin.replace(/\/+$/, "");
}

export function getApiOrigin(): string {
  return apiOrigin;
}

/** Registered by the auth store; the client asks it for the current access token. */
export function setTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

type UnauthorizedHandler = () => Promise<unknown>;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/** Registered by the auth store: runs the shared refresh after a NOT_AUTHENTICATED 401. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  timeoutMs?: number;
  signal?: AbortSignal;
  /** Extra request headers (for example X-Refresh-Attempt). */
  headers?: Record<string, string>;
}

interface InternalOptions extends RequestOptions {
  /** Read the success body as a Blob instead of JSON (`apiBlob`). */
  blob?: boolean;
  /** Skip the 401 handler (refresh and logout). */
  raw?: boolean;
  /** This request was already retried after a refresh (BR6.4: retry budget of one). */
  retried?: boolean;
}

interface ErrorEnvelope {
  error?: { code?: unknown; message?: unknown; details?: unknown; requestId?: unknown };
}

function retryAfter(response: Response): number | null {
  const value = response.headers.get("Retry-After");
  if (!value) return null;
  const seconds = Number.parseInt(value, 10);
  return Number.isFinite(seconds) ? seconds : null;
}

async function toApiError(response: Response): Promise<ApiError> {
  const headerRequestId = response.headers.get("X-Request-ID");
  let envelope: ErrorEnvelope = {};
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    envelope = {};
  }
  const error = envelope.error ?? {};
  return new ApiError({
    status: response.status,
    code: normaliseCode(error.code),
    message: typeof error.message === "string" ? error.message : "Something went wrong.",
    details: Array.isArray(error.details) ? (error.details as ErrorDetail[]) : [],
    requestId: typeof error.requestId === "string" ? error.requestId : headerRequestId,
    retryAfterSeconds: retryAfter(response),
  });
}

/** Perform one request and return the parsed JSON body (or `undefined` for 204). */
export function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return send<T>(path, options);
}

/** Perform one request and return the body as a Blob (owner-checked media, U4). */
export function apiBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  return send<Blob>(path, { ...options, blob: true });
}

/** Like `apiRequest`, but a 401 is returned as it is (no refresh). For refresh and logout. */
export function apiRaw<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return send<T>(path, { ...options, raw: true });
}

async function send<T>(path: string, options: InternalOptions): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onAbort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  options.signal?.addEventListener("abort", onAbort);

  const multipart = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...options.headers,
    Accept: options.blob ? "*/*" : "application/json",
    "X-Requested-With": "XMLHttpRequest",
  };
  if (options.body !== undefined && !multipart) headers["Content-Type"] = "application/json";
  const token = tokenProvider();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${apiOrigin}${path}`, {
      method: options.method ?? (options.body === undefined ? "GET" : "POST"),
      headers,
      body:
        options.body === undefined
          ? undefined
          : multipart
            ? (options.body as FormData)
            : JSON.stringify(options.body),
      credentials: "include",
      signal: controller.signal,
    });
  } catch {
    throw new ApiError({
      status: 0,
      code: timedOut ? "TIMEOUT" : "NETWORK_ERROR",
      message: timedOut
        ? "The server took too long to answer. Please try again."
        : "We couldn't reach the server. Check your connection and try again.",
      requestId: null,
      details: [],
    });
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", onAbort);
  }

  if (!response.ok) {
    const error = await toApiError(response);
    const expired = error.status === 401 && error.code === "NOT_AUTHENTICATED";
    if (expired && !options.raw && !options.retried && unauthorizedHandler) {
      await unauthorizedHandler();
      return send<T>(path, { ...options, retried: true });
    }
    throw error;
  }
  if (response.status === 204) {
    return undefined as T;
  }
  if (options.blob) {
    return (await response.blob()) as T;
  }
  return (await response.json()) as T;
}
