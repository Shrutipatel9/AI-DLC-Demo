// The analysis progress screen (US7.2, US7.11: AC7.2.1-AC7.2.4, AC7.11.1-AC7.11.3).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import {
  COMPLETED,
  FAILED,
  FAILED_TWICE,
  RUNNING,
  WRITING,
  analysisServer,
  newAnalysisState,
} from "@/test-utils/analysis-server";
import { mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, toastMock } from "@/test-utils/next-mocks";

import { AnalysisProgress } from "./analysis-progress";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

beforeEach(() => {
  resetNextMocks();
  configureApiOrigin("http://api.test");
});

function show(state = newAnalysisState()) {
  const requests = mockFetch(analysisServer(state));
  render(<AnalysisProgress pollIntervalMs={5} />);
  return { state, requests };
}

describe("Progress while the analysis runs (US7.2)", () => {
  it("shows every step's state in words and the leave-and-come-back note (AC7.2.1, AC7.2.2)", async () => {
    show(newAnalysisState({ runs: [WRITING] }));
    expect(await screen.findByTestId("analysis-progress")).toHaveAttribute(
      "data-status",
      "running",
    );
    expect(screen.getByTestId("analysis-step-label")).toHaveTextContent("Step 5 of 5 · Analysis");
    expect(screen.getByTestId("analysis-step-measuring-state")).toHaveTextContent("Done");
    expect(screen.getByTestId("analysis-step-writing-state")).toHaveTextContent("In progress");
    expect(screen.getByTestId("analysis-step-writing")).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("analysis-step-generating_images-state")).toHaveTextContent(
      "Waiting",
    );
    const note = screen.getByTestId("analysis-leave-note");
    expect(note).toHaveTextContent("close this page and come back later");
    expect(note).toHaveTextContent("up to about 8 minutes");
    expect(screen.queryByTestId("analysis-view-report")).not.toBeInTheDocument();
  });

  it("announces step changes politely and never moves focus (AC7.2.1)", async () => {
    const state = newAnalysisState({ runs: [RUNNING] });
    show(state);
    const live = await screen.findByTestId("analysis-announcement");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveAttribute("role", "status");
    await waitFor(() => expect(live).toHaveTextContent("Now: Measuring your features."));
    state.runs = [WRITING];
    await waitFor(() => expect(live).toHaveTextContent("Now: Writing your report."));
    state.runs = [COMPLETED];
    await waitFor(() => expect(live).toHaveTextContent("Your report is ready."));
    expect(document.body).toHaveFocus(); // nothing took focus
  });

  it("shows View my report when ready and says so with a toast (AC7.2.4)", async () => {
    const state = newAnalysisState({ runs: [RUNNING] });
    show(state);
    await screen.findByTestId("analysis-progress");
    expect(screen.queryByTestId("analysis-view-report")).not.toBeInTheDocument();
    state.runs = [COMPLETED];
    const link = await screen.findByTestId("analysis-view-report");
    expect(link).toHaveAttribute("href", "/home");
    expect(link).toHaveTextContent("View my report");
    expect(screen.getByTestId("analysis-title")).toHaveTextContent("Your report is ready");
    await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith("Your report is ready."));
  });

  it("an already finished run (coming back later) shows the report link without a toast (AC7.2.3)", async () => {
    show(newAnalysisState({ runs: [COMPLETED] }));
    expect(await screen.findByTestId("analysis-view-report")).toBeInTheDocument();
    expect(toastMock.success).not.toHaveBeenCalled();
  });

  it("keeps polling until the run ends and then stops", async () => {
    const { requests } = show(newAnalysisState({ runs: [RUNNING, WRITING, COMPLETED] }));
    await screen.findByTestId("analysis-view-report");
    const reads = requests.filter((request) => request.method === "GET").length;
    expect(reads).toBe(3);
    await new Promise((resolve) => setTimeout(resolve, 40));
    expect(requests.filter((request) => request.method === "GET")).toHaveLength(3);
  });
});

describe("Not started, and load errors", () => {
  it("says the analysis has not started and points to the payment screen", async () => {
    show(newAnalysisState({ runs: [] }));
    expect(await screen.findByTestId("analysis-not-started")).toHaveTextContent(
      "starts only when you click Start Analysis",
    );
    expect(screen.getByTestId("analysis-payment-link")).toHaveAttribute("href", "/payment");
  });

  it("offers Try again when the first read fails, then shows the run", async () => {
    const state = newAnalysisState({ runs: [COMPLETED], failReads: true });
    show(state);
    expect(await screen.findByTestId("analysis-error")).toBeInTheDocument();
    state.failReads = false;
    await userEvent.setup().click(screen.getByTestId("analysis-retry-button"));
    expect(await screen.findByTestId("analysis-view-report")).toBeInTheDocument();
  });

  it("keeps the last run when a later poll fails", async () => {
    const state = newAnalysisState({ runs: [WRITING] });
    show(state);
    await screen.findByTestId("analysis-progress");
    state.failReads = true;
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(screen.getByTestId("analysis-progress")).toBeInTheDocument();
    expect(screen.queryByTestId("analysis-error")).not.toBeInTheDocument();
  });
});

describe("A failed run (US7.11)", () => {
  it("explains in plain language and offers one free re-run (AC7.11.1, AC7.11.2)", async () => {
    const state = newAnalysisState({ runs: [FAILED], rerun: RUNNING });
    show(state);
    const message = await screen.findByTestId("analysis-failure-message");
    expect(message).toHaveTextContent("went wrong on our side");
    expect(message).toHaveTextContent("payment still covers this report");
    expect(screen.getByTestId("analysis-step-writing-state")).toHaveTextContent("Didn't finish");
    expect(screen.queryByTestId("analysis-contact-support")).not.toBeInTheDocument();

    state.runs = [WRITING];
    await userEvent.setup().click(screen.getByTestId("analysis-rerun-button"));

    expect(state.reruns).toBe(1);
    expect(await screen.findByTestId("analysis-progress")).toHaveAttribute(
      "data-status",
      "running",
    );
    await waitFor(() =>
      expect(toastMock.success).toHaveBeenCalledWith("We've started your analysis again."),
    );
    expect(screen.queryByTestId("analysis-rerun-button")).not.toBeInTheDocument();
  });

  it("after a second failure only offers contact support (AC7.11.3)", async () => {
    show(newAnalysisState({ runs: [FAILED_TWICE] }));
    expect(await screen.findByTestId("analysis-contact-support")).toHaveTextContent(
      "contact support",
    );
    expect(screen.queryByTestId("analysis-rerun-button")).not.toBeInTheDocument();
    expect(screen.getByTestId("analysis-failure-message")).toHaveTextContent("contact support");
  });

  it("tells the user when the re-run cannot start", async () => {
    show(
      newAnalysisState({
        runs: [FAILED],
        rerun: { status: 409, code: "RERUN_NOT_AVAILABLE" },
      }),
    );
    await userEvent.setup().click(await screen.findByTestId("analysis-rerun-button"));
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(
        "We couldn't start the re-run. Please try again.",
      ),
    );
    expect(screen.getByTestId("analysis-rerun-button")).toBeEnabled();
  });

  it("toasts when a run fails while the user is watching", async () => {
    const state = newAnalysisState({ runs: [WRITING] });
    show(state);
    await screen.findByTestId("analysis-progress");
    state.runs = [FAILED];
    await screen.findByTestId("analysis-failed");
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith("Your analysis didn't finish."),
    );
    expect(screen.getByTestId("analysis-announcement")).toHaveTextContent("didn't finish");
  });
});
