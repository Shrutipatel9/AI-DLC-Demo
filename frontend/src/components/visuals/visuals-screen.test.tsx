// The AI Visuals screen (US9.2-US9.5: AC9.2.1, AC9.3.1, AC9.4.1, AC9.4.2, AC9.5.2-AC9.5.5).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import {
  GENERATING_SLOT,
  imagesServer,
  makeImages,
  makeSlots,
  newImagesState,
  unavailable,
} from "@/test-utils/images-server";
import { mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, toastMock } from "@/test-utils/next-mocks";

import { VisualsScreen } from "./visuals-screen";

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

function show(state = newImagesState(), pollIntervalMs = 5) {
  const requests = mockFetch(imagesServer(state));
  render(<VisualsScreen pollIntervalMs={pollIntervalMs} />);
  return { state, requests };
}

describe("The AI Visuals (US9.2-US9.4)", () => {
  it("shows 5 hairstyles and 5 outfits, each labelled as an AI illustration (AC9.2.1, AC9.3.1)", async () => {
    show();
    const hairstyles = await screen.findByTestId("visuals-hairstyle");
    expect(within(hairstyles).getAllByRole("listitem")).toHaveLength(5);
    const outfits = screen.getByTestId("visuals-outfit");
    expect(within(outfits).getAllByRole("listitem")).toHaveLength(5);
    for (const group of [hairstyles, outfits]) {
      const labels = within(group).getAllByText("AI-generated illustration");
      expect(labels).toHaveLength(5);
    }
    expect(screen.getByTestId("visuals-intro")).toHaveTextContent("AI-generated illustration");
  });

  it("stacks the aging cards: my own photo first, then +3, +5 and +10 labelled (AC9.4.1, AC9.4.2)", async () => {
    show();
    const aging = await screen.findByTestId("visuals-aging");
    const cards = within(aging).getAllByRole("listitem");
    expect(cards).toHaveLength(4);
    expect(cards.map((card) => card.getAttribute("data-testid"))).toEqual([
      "visual-aging-now",
      "visual-aging_plus_3",
      "visual-aging_plus_5",
      "visual-aging_plus_10",
    ]);
    expect(within(cards[0]).queryByText("AI-generated illustration")).toBeNull(); // not generated
    expect(within(cards[0]).getByText("Now (your photo)")).toBeInTheDocument();
    for (const card of cards.slice(1)) {
      expect(within(card).getByText("AI-generated illustration")).toBeInTheDocument();
    }
    // 5 + 5 + 3 generated images on the screen (AC9.4.2); the 11 feature images belong to the report.
    expect(screen.getAllByText("AI-generated illustration")).toHaveLength(13);
  });

  it("loads each private image through the API client with the access token (FE-004)", async () => {
    const { requests } = show();
    await screen.findByTestId("visual-image-hairstyle_1");
    await waitFor(() =>
      expect(screen.getByTestId("visual-image-hairstyle_1")).toHaveAttribute(
        "data-state",
        "loaded",
      ),
    );
    expect(requests.some((request) => request.url.endsWith("/media/hairstyle_1"))).toBe(true);
  });

  it("polls while images are being created, then shows them (AC9.5.5)", async () => {
    show(
      newImagesState({
        reads: [makeImages({ hairstyle_1: GENERATING_SLOT }, { generating: true }), makeImages()],
      }),
      300,
    );
    expect(await screen.findByTestId("visual-busy-hairstyle_1")).toBeInTheDocument();
    expect(screen.getByTestId("visuals-announcement")).toHaveTextContent("still being created");
    expect(await screen.findByTestId("visual-image-hairstyle_1")).toBeInTheDocument();
    expect(screen.getByTestId("visuals-announcement")).toHaveTextContent("ready");
  });
});

describe("An image that failed (US9.5)", () => {
  const failed = (retriesLeft = 3) => makeImages({ hairstyle_2: unavailable(retriesLeft) });

  it("says not available yet with a retry button (AC9.5.2)", async () => {
    show(newImagesState({ reads: [failed()] }));
    const card = await screen.findByTestId("visual-unavailable-hairstyle_2");
    expect(card).toHaveTextContent("Not available yet");
    expect(screen.getByTestId("visual-retry-hairstyle_2")).toBeEnabled();
    expect(screen.getByTestId("visual-retry-help-hairstyle_2")).toHaveTextContent("3 retries left");
  });

  it("shows the new image after a successful retry (AC9.5.3)", async () => {
    const ready = makeSlots()[12]; // hairstyle_2
    const { state } = show(
      newImagesState({ reads: [failed()], retry: { ...ready, retriesLeft: 2 } }),
    );
    await userEvent.click(await screen.findByTestId("visual-retry-hairstyle_2"));

    expect(await screen.findByTestId("visual-image-hairstyle_2")).toBeInTheDocument();
    expect(state.retries).toEqual(["hairstyle_2"]);
    expect(toastMock.success).toHaveBeenCalledWith("Your image is ready.");
    expect(toastMock.error).not.toHaveBeenCalled();
  });

  it("shows an error toast and keeps the slot marked when the retry fails (AC9.5.3)", async () => {
    const stillFailed = { ...unavailable(2), slotId: "hairstyle_2", group: "hairstyle" as const };
    show(
      newImagesState({
        reads: [failed()],
        retry: { ...makeSlots()[12], ...stillFailed },
      }),
    );
    await userEvent.click(await screen.findByTestId("visual-retry-hairstyle_2"));

    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(expect.stringContaining("couldn't")),
    );
    expect(await screen.findByTestId("visual-unavailable-hairstyle_2")).toBeInTheDocument();
    expect(screen.getByTestId("visual-retry-help-hairstyle_2")).toHaveTextContent("2 retries left");
  });

  it("disables the retry button once 3 retries are used, so no request is made (AC9.5.4)", async () => {
    const { state } = show(newImagesState({ reads: [failed(0)] }));
    const button = await screen.findByTestId("visual-retry-hairstyle_2");
    expect(button).toBeDisabled();
    expect(screen.getByTestId("visual-retry-help-hairstyle_2")).toHaveTextContent(
      "No retries left",
    );
    await userEvent.click(button);
    expect(state.retries).toEqual([]);
  });

  it("tells the user when the server refuses a retry and reads the counts again", async () => {
    const { state } = show(
      newImagesState({
        reads: [failed(), failed(0)],
        retry: { status: 409, code: "IMAGE_RETRY_NOT_AVAILABLE" },
      }),
    );
    await userEvent.click(await screen.findByTestId("visual-retry-hairstyle_2"));

    await waitFor(() => expect(toastMock.error).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("visual-retry-hairstyle_2")).toBeDisabled());
    expect(state.retries).toEqual(["hairstyle_2"]);
  });
});

describe("Other states", () => {
  it("points to the analysis when none was started (404)", async () => {
    show(newImagesState({ reads: [] }));
    expect(await screen.findByTestId("visuals-none")).toBeInTheDocument();
    expect(screen.getByTestId("visuals-analysis-link")).toHaveAttribute("href", "/analysis");
  });

  it("offers Try again when the first read fails", async () => {
    const state = newImagesState({ failReads: true });
    show(state);
    expect(await screen.findByTestId("visuals-error")).toBeInTheDocument();
    state.failReads = false;
    await userEvent.click(screen.getByTestId("visuals-retry-button"));
    expect(await screen.findByTestId("visuals")).toBeInTheDocument();
  });
});
