// Private photos are read with the access token and shown from a revocable blob: URL
// (AC1.10.2); a failed read shows a placeholder instead of a broken image.
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin, setTokenProvider } from "@/lib/api/client";
import { errorResponse, mockFetch } from "@/test-utils/fetch-mock";

import { AngleIllustration } from "./illustrations";
import { reasonMessage } from "./messages";
import { PhotoThumbnail } from "./photo-thumbnail";

const originalCreate = URL.createObjectURL;
const originalRevoke = URL.revokeObjectURL;

beforeEach(() => {
  configureApiOrigin("http://api.test");
  setTokenProvider(() => "tok");
  URL.createObjectURL = vi.fn(() => "blob:photo-1");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  URL.createObjectURL = originalCreate;
  URL.revokeObjectURL = originalRevoke;
});

describe("PhotoThumbnail", () => {
  it("loads the photo with the token and revokes its URL on unmount", async () => {
    const requests = mockFetch(
      () => new Response("png", { status: 200, headers: { "Content-Type": "image/png" } }),
    );
    const { unmount } = render(
      <PhotoThumbnail imageUrl="/media/f1" alt="Your Front photo" testId="thumb" />,
    );
    expect(screen.getByTestId("thumb")).toHaveAttribute("data-state", "loading");
    expect(await screen.findByAltText("Your Front photo")).toHaveAttribute("src", "blob:photo-1");
    expect(requests[0].headers.authorization).toBe("Bearer tok");
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:photo-1");
  });

  it("shows a placeholder when the photo cannot be read", async () => {
    mockFetch(() => errorResponse(404, "NOT_FOUND"));
    render(<PhotoThumbnail imageUrl="/media/gone" alt="Your Front photo" testId="thumb" />);
    await waitFor(() =>
      expect(screen.getByTestId("thumb")).toHaveAttribute("data-state", "failed"),
    );
    expect(screen.getByText("Your Front photo (could not be shown)")).toBeInTheDocument();
  });
});

describe("illustrations and messages", () => {
  it("draws a labelled example for each direction", () => {
    render(
      <>
        <AngleIllustration direction="front" title="Example: Front" />
        <AngleIllustration direction="left" title="Example: Left" />
        <AngleIllustration direction="right" />
      </>,
    );
    expect(screen.getByRole("img", { name: "Example: Front" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Example: Left" })).toBeInTheDocument();
  });

  it("every reason describes the photo and a fix, never the person", () => {
    const reasons = [
      "UNREADABLE",
      "TOO_SMALL",
      "NO_FACE",
      "MULTIPLE_FACES",
      "TOO_DARK",
      "TOO_BRIGHT",
      "FACE_TOO_SMALL",
      "FACE_TOO_LARGE",
      "POSE_MISMATCH",
      "EYES_COVERED",
      "MOUTH_COVERED",
      "SOMETHING_NEW",
    ];
    for (const reason of reasons) {
      const message = reasonMessage(reason, undefined);
      expect(message.length).toBeGreaterThan(20);
      expect(message).not.toMatch(
        /ugly|attractive|beautiful|skin tone|weight|wrinkle|nose is|jaw is/i,
      );
    }
    expect(reasonMessage("POSE_MISMATCH", undefined)).toContain("requested angle");
  });
});
