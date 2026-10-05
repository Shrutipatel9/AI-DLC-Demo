// Test helper: replace `fetch` with explicit per-test handlers. Any request no handler
// answers fails the test (NFR8.2): nothing can reach the network.
import { vi } from "vitest";

export interface RecordedRequest {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
  /** The body exactly as passed to fetch (for example a FormData upload). */
  rawBody: BodyInit | null | undefined;
  credentials: RequestCredentials | undefined;
}

type Handler = (request: RecordedRequest) => Response | Promise<Response> | undefined;

export function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function errorResponse(
  status: number,
  code: string,
  options: { details?: unknown[]; requestId?: string; headers?: Record<string, string> } = {},
) {
  return jsonResponse(
    status,
    {
      error: {
        code,
        message: "server message",
        details: options.details ?? [],
        requestId: options.requestId ?? "req-123",
      },
    },
    options.headers,
  );
}

/** Install handlers; returns the list of requests the code under test made. */
export function mockFetch(...handlers: Handler[]): RecordedRequest[] {
  const requests: RecordedRequest[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const headers = Object.fromEntries(new Headers(init.headers).entries());
      const request: RecordedRequest = {
        url,
        method: init.method ?? "GET",
        headers,
        body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
        rawBody: init.body,
        credentials: init.credentials,
      };
      requests.push(request);
      if (init.signal?.aborted) throw new DOMException("Aborted", "AbortError");
      for (const handler of handlers) {
        const response = await handler(request);
        if (response) return response;
      }
      throw new Error(`Unhandled fetch in test: ${request.method} ${url}`);
    }),
  );
  return requests;
}

/** Match a method and path suffix. */
export function route(
  method: string,
  path: string,
  respond: () => Response | Promise<Response>,
): Handler {
  return (request) =>
    request.method === method && new URL(request.url, "http://x").pathname === path
      ? respond()
      : undefined;
}
