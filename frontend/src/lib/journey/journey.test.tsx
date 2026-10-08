// The journey rule on the client: which page shows each step, the route guard and "go to my next
// step" (US11.8, US5.7, US2.1). The server decides the step; these tests use a stand-in for it.
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";

import { useGoToNextStep, useJourneyGuard } from "./hooks";
import type { Step } from "./api";
import { STAGE, isTooEarly, routeForStep } from "./routes";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});

function serverSays(step: Step, flaggedAngles: string[] = []) {
  return mockFetch(
    route("GET", "/journey/next-step", () => jsonResponse(200, { step, flaggedAngles })),
  );
}

describe("journey routes", () => {
  it("opens the page of each step", () => {
    expect(routeForStep("consent")).toBe("/onboarding");
    expect(routeForStep("questionnaire")).toBe("/onboarding");
    expect(routeForStep("photos")).toBe("/photos");
    expect(routeForStep("payment")).toBe("/payment");
    expect(routeForStep("confirming_payment")).toBe("/payment/success");
    expect(routeForStep("start_analysis")).toBe("/analysis");
    expect(routeForStep("progress")).toBe("/analysis");
    expect(routeForStep("home")).toBe("/home");
  });

  it("treats a page as too early only when it is a later step than the user's next one", () => {
    expect(isTooEarly(STAGE.home, "photos")).toBe(true);
    expect(isTooEarly(STAGE.payment, "questionnaire")).toBe(true);
    expect(isTooEarly(STAGE.analysis, "payment")).toBe(true);
    expect(isTooEarly(STAGE.photos, "photos")).toBe(false);
    expect(isTooEarly(STAGE.photos, "payment")).toBe(false); // a retake from payment is allowed
    expect(isTooEarly(STAGE.confirming, "confirming_payment")).toBe(false);
    expect(isTooEarly(STAGE.analysis, "home")).toBe(false);
  });
});

describe("useJourneyGuard", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("sends the user to the next step when this page comes later (AC11.8.2)", async () => {
    serverSays("photos", ["right_3q"]);
    const { result } = renderHook(() => useJourneyGuard(STAGE.home));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/photos"));
    expect(result.current).toBe("checking");
  });

  it("lets the page render when it is the next step or an earlier one", async () => {
    serverSays("payment");
    const { result } = renderHook(() => useJourneyGuard(STAGE.photos));
    await waitFor(() => expect(result.current).toBe("allowed"));
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("asks once per page load and not again when the page re-renders (AC5.7.2)", async () => {
    const requests = serverSays("payment");
    const { result, rerender } = renderHook(() => useJourneyGuard(STAGE.photos));
    await waitFor(() => expect(result.current).toBe("allowed"));
    rerender();
    rerender();
    expect(requests.filter((request) => request.url.endsWith("/journey/next-step"))).toHaveLength(
      1,
    );
  });

  it("lets the page render and report its own error when the next step cannot be read", async () => {
    mockFetch(route("GET", "/journey/next-step", () => errorResponse(500, "INTERNAL_ERROR")));
    const { result } = renderHook(() => useJourneyGuard(STAGE.home));
    await waitFor(() => expect(result.current).toBe("allowed"));
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("useGoToNextStep", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("opens the page of the user's next step (AC2.1.3)", async () => {
    serverSays("confirming_payment");
    const { result } = renderHook(() => useGoToNextStep());
    await result.current();
    expect(router.push).toHaveBeenCalledWith("/payment/success");
  });

  it("falls back to the home page, whose guard finds the step, when the server cannot say", async () => {
    mockFetch(route("GET", "/journey/next-step", () => errorResponse(503, "UPSTREAM_UNAVAILABLE")));
    const { result } = renderHook(() => useGoToNextStep());
    await result.current();
    expect(router.push).toHaveBeenCalledWith("/home");
  });
});
