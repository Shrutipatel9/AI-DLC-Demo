// Global test setup.
// - jest-dom matchers for React Testing Library.
// - A global `fetch` stub that FAILS any request a test did not explicitly handle, so no
//   unit test can reach the network (NFR8.2, BR8.7, AC1.3.3). Tests install their own
//   handlers with `vi.stubGlobal("fetch", ...)`.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

function unhandledFetch(input: RequestInfo | URL): Promise<Response> {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  return Promise.reject(new Error(`Unhandled fetch in test: ${url}`));
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(unhandledFetch));
});

afterEach(() => {
  cleanup();
});
