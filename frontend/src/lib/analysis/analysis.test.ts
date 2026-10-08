// The analysis API functions and the progress hook (US7.1, US7.2, US7.11).
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import {
  COMPLETED,
  FAILED,
  RUNNING,
  WRITING,
  analysisServer,
  newAnalysisState,
} from "@/test-utils/analysis-server";
import { mockFetch } from "@/test-utils/fetch-mock";

import { getCurrentRun, rerunAnalysis, startAnalysis, useAnalysisProgress } from "./index";

beforeEach(() => {
  configureApiOrigin("http://api.test");
});

describe("analysis API functions", () => {
  it("start, read and re-run use the contract's routes through the API client", async () => {
    const state = newAnalysisState({ runs: [WRITING], start: RUNNING, rerun: RUNNING });
    const requests = mockFetch(analysisServer(state));

    expect((await startAnalysis()).status).toBe("running");
    expect((await getCurrentRun()).steps[1].state).toBe("current");
    expect((await rerunAnalysis()).runId).toBe(RUNNING.runId);

    expect(requests.map((request) => `${request.method} ${new URL(request.url).pathname}`)).toEqual(
      ["POST /analysis/runs", "GET /analysis/runs/current", "POST /analysis/runs/current/rerun"],
    );
    for (const request of requests) {
      expect(request.credentials).toBe("include");
      expect(request.headers["x-requested-with"]).toBe("XMLHttpRequest");
    }
  });
});

describe("useAnalysisProgress", () => {
  it("follows a run until it completes and then stops polling", async () => {
    const requests = mockFetch(analysisServer(newAnalysisState({ runs: [RUNNING, COMPLETED] })));
    const { result } = renderHook(() => useAnalysisProgress(5));

    expect(result.current.phase).toBe("loading");
    await waitFor(() => expect(result.current.phase).toBe("completed"));
    expect(requests.filter((request) => request.method === "GET")).toHaveLength(2);
  });

  it("re-runs after a failure and follows the new run", async () => {
    const state = newAnalysisState({ runs: [FAILED], rerun: RUNNING });
    mockFetch(analysisServer(state));
    const { result } = renderHook(() => useAnalysisProgress(5));
    await waitFor(() => expect(result.current.phase).toBe("failed"));

    state.runs = [WRITING, COMPLETED];
    let started = false;
    await act(async () => {
      started = await result.current.rerun();
    });

    expect(started).toBe(true);
    await waitFor(() => expect(result.current.phase).toBe("completed"));
  });

  it("reports a refused re-run as false", async () => {
    mockFetch(
      analysisServer(
        newAnalysisState({ runs: [FAILED], rerun: { status: 409, code: "RERUN_NOT_AVAILABLE" } }),
      ),
    );
    const { result } = renderHook(() => useAnalysisProgress(5));
    await waitFor(() => expect(result.current.phase).toBe("failed"));
    let started = true;
    await act(async () => {
      started = await result.current.rerun();
    });
    expect(started).toBe(false);
    expect(result.current.phase).toBe("failed");
  });

  it("says none for a 404 and error for a failed first read, and reload tries again", async () => {
    const none = newAnalysisState({ runs: [] });
    mockFetch(analysisServer(none));
    const first = renderHook(() => useAnalysisProgress(5));
    await waitFor(() => expect(first.result.current.phase).toBe("none"));
    first.unmount();

    const broken = newAnalysisState({ runs: [COMPLETED], failReads: true });
    mockFetch(analysisServer(broken));
    const second = renderHook(() => useAnalysisProgress(5));
    await waitFor(() => expect(second.result.current.phase).toBe("error"));
    broken.failReads = false;
    act(() => second.result.current.reload());
    await waitFor(() => expect(second.result.current.phase).toBe("completed"));
  });
});
