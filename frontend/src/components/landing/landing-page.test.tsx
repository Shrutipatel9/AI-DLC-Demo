// The landing page (US2.1, US2.2; FR-001).
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, type User } from "@/lib/auth/store";
import { jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";

import { HOW_IT_WORKS, LandingPage } from "./landing-page";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});

const USER: User = {
  id: "u-1",
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  role: "user",
  memberSince: "2026-10-01T10:00:00Z",
};

function stubMotion(reduce: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: reduce && query.includes("reduce"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

describe("LandingPage", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
    stubMotion(true);
  });

  it("offers Get started and a separate header Sign in link to the login screen (AC2.1.1, AC2.1.2)", () => {
    render(<LandingPage />);
    expect(screen.getByTestId("landing-get-started")).toHaveTextContent("Get started");
    expect(screen.getByTestId("landing-get-started")).toHaveAttribute("href", "/signup");
    const signIn = screen.getByTestId("landing-signin-link");
    expect(signIn).toHaveTextContent("Sign in");
    expect(signIn).toHaveAttribute("href", "/login");
    expect(screen.getByRole("navigation", { name: "Main" })).toContainElement(signIn);
  });

  it("takes a signed-in user to their next step with Get started (AC2.1.3)", async () => {
    act(() => setSession("tok", "2099-01-01T00:00:00Z", USER));
    mockFetch(
      route("GET", "/journey/next-step", () =>
        jsonResponse(200, { step: "payment", flaggedAngles: [] }),
      ),
    );
    render(<LandingPage />);
    expect(screen.queryByTestId("landing-signin-link")).toBeNull();
    await userEvent.setup().click(screen.getByTestId("landing-get-started"));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/payment"));
  });

  it("lists questionnaire, photos, analysis, report in that order (AC2.2.1)", () => {
    render(<LandingPage />);
    const steps = screen.getAllByTestId(/^how-step-/);
    expect(steps).toHaveLength(4);
    expect(steps.map((step) => step.querySelector("h3")?.textContent)).toEqual(
      HOW_IT_WORKS.map((step) => step.title),
    );
    expect(HOW_IT_WORKS.map((step) => step.title.split(" ").slice(-1)[0])).toEqual([
      "questionnaire",
      "photos",
      "face",
      "report",
    ]);
  });

  it("shows the steps without waiting for scrolling under reduced motion (AC2.2.2)", async () => {
    render(<LandingPage />);
    await waitFor(() => {
      for (const step of screen.getAllByTestId(/^how-step-/)) {
        expect(step).toHaveAttribute("data-shown", "true");
      }
    });
  });

  it("reveals each step as it scrolls into view when motion is allowed (AC2.2.1)", async () => {
    stubMotion(false);
    const callbacks: Array<(entries: Array<{ isIntersecting: boolean }>) => void> = [];
    class FakeObserver {
      constructor(callback: (entries: Array<{ isIntersecting: boolean }>) => void) {
        callbacks.push(callback);
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal("IntersectionObserver", FakeObserver);

    render(<LandingPage />);
    const steps = screen.getAllByTestId(/^how-step-/);
    expect(steps.every((step) => step.getAttribute("data-shown") === "false")).toBe(true);

    const [first] = callbacks;
    act(() => first([{ isIntersecting: true }]));
    expect(steps[0]).toHaveAttribute("data-shown", "true");
    expect(steps[1]).toHaveAttribute("data-shown", "false");
  });
});
