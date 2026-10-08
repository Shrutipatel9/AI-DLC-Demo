// Home Overview (US11.1, US11.3: AC11.1.1-AC11.1.4, AC11.3.1) through the real HomeView.
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HomeView } from "@/components/app/home-view";
import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, type User } from "@/lib/auth/store";
import { jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, toastMock } from "@/test-utils/next-mocks";
import { makeHome, newReportState, reportServer } from "@/test-utils/report-server";

import { durationText } from "./home-overview";
import { RadarChart, valueText } from "./radar-chart";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const USER: User = {
  id: "u-1",
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  role: "user",
  memberSince: "2026-10-01T10:00:00Z",
};

beforeEach(() => {
  resetAuthStore();
  resetSession();
  resetNextMocks();
  configureApiOrigin("http://api.test");
  act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
});

function show(state = newReportState()) {
  const requests = mockFetch(
    route("GET", "/auth/me", () => jsonResponse(200, USER)),
    reportServer(state),
  );
  render(<HomeView />);
  return { state, requests };
}

describe("Home Overview", () => {
  it("shows stats, before/potential, priorities, protocol and radar once a report exists (AC11.1.2)", async () => {
    show();
    const overview = await screen.findByTestId("home-overview");
    expect(screen.getByTestId("home-greeting")).toHaveTextContent("Hi, Maya Test");
    expect(screen.getByTestId("home-status")).toHaveTextContent("Your report is ready.");
    expect(screen.getByTestId("home-stat-score")).toHaveTextContent("77/100");
    expect(screen.getByTestId("home-stat-points")).toHaveTextContent("42 points");
    expect(screen.getByTestId("home-stat-time")).toHaveTextContent("1 min 12 s");
    expect(within(overview).getByText("Before")).toBeInTheDocument();
    expect(within(overview).getByText("Potential")).toBeInTheDocument();
    expect(within(screen.getByTestId("home-priorities")).getAllByText(/\/100/)).toHaveLength(3);
    expect(screen.getByTestId("home-priority-nose")).toHaveTextContent(
      "Nose · 48/100 · Needs attention",
    );
    expect(screen.getByTestId("home-priority-nose")).toHaveTextContent(
      "Nose width: wider or larger than typical",
    );
    expect(screen.getByTestId("radar-chart")).toBeInTheDocument();
  });

  it("lists the radar values as text, and an unmeasured axis as Not measured (AC11.1.4)", async () => {
    show();
    const values = await screen.findByTestId("radar-values");
    expect(values).toHaveTextContent("Symmetry");
    expect(values).toHaveTextContent("88 out of 100");
    expect(values).toHaveTextContent("Smoothness");
    expect(within(values).getByText("Not measured")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Harmony Profile radar chart/ })).toBeInTheDocument();
  });

  it("shows the Phase 01 protocol card with actions from the recommendations (AC11.3.1)", async () => {
    show();
    const card = await screen.findByTestId("home-protocol");
    expect(card).toHaveTextContent("PHASE 01");
    expect(card).toHaveTextContent("Foundation and Everyday Care");
    expect(card).toHaveTextContent("Immediate to weeks 1-12");
    expect(screen.getByTestId("home-protocol-actions")).toHaveTextContent("Skin: Drink water.");
    expect(card).toHaveTextContent("This phase comes first.");
  });

  it("links to the report and downloads the PDF from Home (AC11.1.3)", async () => {
    const created = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:pdf");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const { state } = show();

    expect(await screen.findByTestId("home-report-link")).toHaveAttribute("href", "/report");
    await userEvent.click(screen.getByTestId("home-download-pdf"));

    await waitFor(() => expect(state.pdfRequests).toBe(1));
    await waitFor(() => expect(toastMock.success).toHaveBeenCalled());
    expect(created).toHaveBeenCalled();
  });

  it("copes with no scores, no potential image and no actions", async () => {
    show(
      newReportState({
        home: makeHome({
          overallScore: null,
          analysisDurationSeconds: null,
          priorityFeatures: [],
          potentialImageUrl: null,
          protocol: {
            phaseLabel: "PHASE 01",
            title: "T",
            timing: "x",
            actions: [],
            closing: "c",
          },
        }),
      }),
    );
    expect(await screen.findByTestId("home-stat-score")).toHaveTextContent("Not scored");
    expect(screen.getByTestId("home-stat-time")).toHaveTextContent("Not recorded");
    expect(screen.getByText("No feature could be scored from your photos.")).toBeInTheDocument();
    expect(screen.getByTestId("home-before-potential")).toHaveTextContent("Not available yet");
    expect(screen.queryByTestId("home-protocol-actions")).toBeNull();
  });

  it("keeps the existing home when there is no report yet (404) (AC11.1.1 otherwise)", async () => {
    show(newReportState({ home: { status: 404, code: "REPORT_NOT_READY" } }));
    expect(await screen.findByTestId("home-next-step-button")).toBeInTheDocument();
    expect(screen.getByTestId("home-greeting")).toHaveTextContent("Hi, Maya Test");
    expect(screen.queryByTestId("home-overview")).toBeNull();
  });
});

describe("Home helpers", () => {
  it("writes the analysis time in words", () => {
    expect(durationText(null)).toBe("Not recorded");
    expect(durationText(45)).toBe("45 s");
    expect(durationText(120)).toBe("2 min");
    expect(durationText(135)).toBe("2 min 15 s");
  });

  it("never plots a missing axis as 0", () => {
    const axes = makeHome().harmonyProfile;
    const { container } = render(<RadarChart axes={axes} />);
    expect(valueText({ axis: "Smoothness", value: null })).toBe("Not measured");
    expect(container.querySelectorAll("circle")).toHaveLength(5);
  });
});
