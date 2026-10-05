// Photo flow: requirements, per-angle upload and camera capture, rejection reasons, and the
// same-person review gate (US5.1, US5.2, US5.3, US5.5, US5.10, US5.11; AC5.1.1-AC5.1.2,
// AC5.2.1-AC5.2.6, AC5.3.1-AC5.3.4, AC5.5.4, AC5.10.1, AC5.11.1-AC5.11.5).
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, mockFetch, type RecordedRequest } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";
import {
  newPhotosState,
  photosServer,
  withPhotos,
  type PhotosServerState,
} from "@/test-utils/photos-server";

import { PhotoFlow } from "./photo-flow";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

function png(name: string, size = 1000): File {
  return new File([new Uint8Array(size)], name, { type: "image/png" });
}

function start(state: PhotosServerState, ...extra: Parameters<typeof mockFetch>) {
  const requests = mockFetch(...extra, photosServer(state));
  render(<PhotoFlow />);
  return requests;
}

async function toFirstStep(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByTestId("photo-requirements-continue"));
  return screen.findByTestId("photo-step");
}

async function uploadAs(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.upload(screen.getByTestId("photo-file-input"), png(name));
}

function setCamera(getUserMedia: (() => Promise<MediaStream>) | undefined) {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: getUserMedia ? { getUserMedia: vi.fn(getUserMedia) } : undefined,
  });
}

function fakeStream(): MediaStream {
  const track = { stop: vi.fn() };
  return { getTracks: () => [track] } as unknown as MediaStream;
}

const originalCreate = URL.createObjectURL;
const originalRevoke = URL.revokeObjectURL;

beforeEach(() => {
  resetNextMocks();
  configureApiOrigin("http://api.test");
  let counter = 0;
  URL.createObjectURL = vi.fn(() => `blob:test-${++counter}`);
  URL.revokeObjectURL = vi.fn();
  setCamera(undefined);
});

afterEach(() => {
  URL.createObjectURL = originalCreate;
  URL.revokeObjectURL = originalRevoke;
});

describe("Requirements first (US5.1)", () => {
  it("shows the 7 rules with their example illustrations, then the configured angles", async () => {
    start(newPhotosState());
    const screenEl = await screen.findByTestId("photo-requirements");
    for (const rule of [
      "no_glasses_hat",
      "even_light",
      "white_background",
      "hair_back",
      "no_makeup",
      "no_neck_cover",
      "no_filters",
    ]) {
      expect(within(screenEl).getByTestId(`photo-rule-${rule}`)).toBeInTheDocument();
      expect(within(screenEl).getByTestId(`photo-rule-illustration-${rule}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId("photo-angle-list")).toHaveTextContent(
      "1. Front2. Left 3/43. Right 3/4",
    );
    expect(screen.getByTestId("photos-step-label")).toHaveTextContent("Step 3 of 5 · Photos");
  });

  it("asks for the configured angles in order, each with its instruction and guidance", async () => {
    start(newPhotosState());
    const user = userEvent.setup();
    await toFirstStep(user);
    expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Photo 1 of 3: Front");
    expect(screen.getByTestId("photo-instruction")).toHaveTextContent("Face the camera head-on.");
    expect(screen.getByTestId("photo-guidance")).toHaveTextContent("Keep a neutral expression");
    expect(screen.getByTestId("photo-progress")).toHaveTextContent("0 of 3 photos done");
    expect(screen.getByRole("img", { name: "Example: Front" })).toBeInTheDocument();
  });

  it("explains when the questionnaire is not submitted yet", async () => {
    start(newPhotosState({ submitted: false }));
    expect(await screen.findByTestId("photos-not-ready")).toBeInTheDocument();
    expect(screen.getByTestId("photos-onboarding-link")).toHaveAttribute("href", "/onboarding");
  });

  it("reports a load failure and retries", async () => {
    let fail = true;
    start(newPhotosState(), (request: RecordedRequest) =>
      fail && request.url.endsWith("/photos") ? errorResponse(500, "INTERNAL_ERROR") : undefined,
    );
    expect(await screen.findByTestId("photos-error")).toBeInTheDocument();
    expect(toastMock.error).toHaveBeenCalled();
    fail = false;
    await userEvent.setup().click(screen.getByTestId("photos-retry-button"));
    expect(await screen.findByTestId("photo-requirements")).toBeInTheDocument();
  });
});

describe("Upload per angle (US5.2)", () => {
  it("uploads each angle, shows a checking state, announces results and counts progress", async () => {
    const state = newPhotosState();
    state.hold = true;
    const requests = start(state);
    const user = userEvent.setup();
    await toFirstStep(user);
    await uploadAs(user, "person-a-front.png");
    expect(await screen.findByTestId("photo-checking")).toHaveTextContent("Checking your photo…");
    expect(screen.getByTestId("photo-upload-button")).toBeDisabled();
    expect(screen.getByTestId("photo-announcement")).toHaveTextContent(
      "Checking your Front photo…",
    );
    act(() => state.release());
    await waitFor(() =>
      expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Photo 2 of 3: Left 3/4"),
    );
    expect(screen.getByTestId("photo-progress")).toHaveTextContent("1 of 3 photos done");
    expect(screen.getByTestId("photo-announcement")).toHaveTextContent(
      "Front photo accepted. Next: Left 3/4.",
    );
    expect(toastMock.success).toHaveBeenCalledWith("Front photo accepted.");
    const put = requests.find((r) => r.method === "PUT");
    expect(put?.url).toBe("http://api.test/photos/front");
    expect(put?.rawBody).toBeInstanceOf(FormData);
    expect((put?.rawBody as FormData).get("captureMethod")).toBe("upload");
    expect(put?.headers["content-type"]).toBeUndefined(); // the browser sets the boundary
  });

  it("finishes on the review screen once every angle is accepted", async () => {
    start(newPhotosState());
    const user = userEvent.setup();
    await toFirstStep(user);
    for (const [index, name] of ["front", "left", "right"].entries()) {
      await uploadAs(user, `person-a-${name}.png`);
      if (index < 2) {
        await waitFor(() =>
          expect(screen.getByTestId("photo-progress")).toHaveTextContent(
            `${index + 1} of 3 photos done`,
          ),
        );
      }
    }
    expect(await screen.findByTestId("photo-review")).toBeInTheDocument();
    expect(screen.getByTestId("review-status")).toHaveTextContent("All 3 photos look good.");
  });

  it("refuses a wrong file type or an oversized file before uploading", async () => {
    const requests = start(newPhotosState());
    const user = userEvent.setup({ applyAccept: false });
    await toFirstStep(user);
    await user.upload(
      screen.getByTestId("photo-file-input"),
      new File(["x"], "face.gif", { type: "image/gif" }),
    );
    expect(screen.getByTestId("photo-reasons")).toHaveTextContent(
      "Please choose a JPEG, PNG or HEIC photo.",
    );
    await user.upload(screen.getByTestId("photo-file-input"), png("big.png", 11 * 1024 * 1024));
    expect(screen.getByTestId("photo-reasons")).toHaveTextContent("larger than 10 MB");
    await user.upload(screen.getByTestId("photo-file-input"), png("empty.png", 0));
    expect(screen.getByTestId("photo-reasons")).toHaveTextContent("This file is empty.");
    expect(requests.some((r) => r.method === "PUT")).toBe(false);
  });

  it("accepts a HEIC file chosen by its extension", async () => {
    const state = newPhotosState();
    start(state);
    const user = userEvent.setup({ applyAccept: false });
    await toFirstStep(user);
    await user.upload(
      screen.getByTestId("photo-file-input"),
      new File([new Uint8Array(10)], "IMG_0001.HEIC", { type: "" }),
    );
    await waitFor(() => expect(state.uploads).toHaveLength(1));
    expect(state.uploads[0].fileName).toBe("IMG_0001.HEIC");
  });
});

describe("Rejection reasons (US5.5, US5.10)", () => {
  it("lists each reason as a photo-focused fix, with the turn direction for pose", async () => {
    start(newPhotosState());
    const user = userEvent.setup();
    await toFirstStep(user);
    await uploadAs(user, "reject-MULTIPLE_FACES-FACE_TOO_SMALL.png");
    const reasons = await screen.findByTestId("photo-reasons");
    expect(reasons).toHaveTextContent("This photo needs exactly one face.");
    expect(reasons).toHaveTextContent("Move closer so your face fills more of the frame.");
    expect(toastMock.error).toHaveBeenCalledWith(
      "This photo can't be used. See the reasons below.",
    );
    expect(screen.getByTestId("photo-announcement")).toHaveTextContent(
      "Your Front photo can't be used.",
    );
    // Still on the same step, with upload still offered.
    expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Front");
    expect(screen.getByTestId("photo-upload-button")).toBeEnabled();
  });

  it("explains a pose mismatch with the angle's turn hint", async () => {
    start(withPhotos(newPhotosState(), { front: "a" }));
    const user = userEvent.setup();
    await toFirstStep(user);
    expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Left 3/4");
    await uploadAs(user, "reject-POSE_MISMATCH.png");
    expect(await screen.findByTestId("photo-reason-POSE_MISMATCH")).toHaveTextContent(
      "This photo doesn't match the Left 3/4 angle. Turn your head to your right so your left cheek faces the camera.",
    );
  });

  it("shows a stored rejection again after a reload", async () => {
    const state = newPhotosState();
    state.photos.set("front", { status: "rejected", reasons: ["TOO_DARK"] });
    start(state);
    await toFirstStep(userEvent.setup());
    expect(screen.getByTestId("photo-reason-TOO_DARK")).toHaveTextContent(
      "This photo is too dark.",
    );
  });

  it("shows the server message for a refused size", async () => {
    start(newPhotosState(), (request: RecordedRequest) =>
      request.method === "PUT" ? errorResponse(413, "PHOTO_TOO_LARGE") : undefined,
    );
    const user = userEvent.setup();
    await toFirstStep(user);
    await uploadAs(user, "person-a.png");
    expect(await screen.findByTestId("photo-reasons")).toHaveTextContent("server message");
  });
});

describe("Camera capture (US5.3)", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLMediaElement.prototype, "play", {
      configurable: true,
      value: vi.fn(() => Promise.resolve()),
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
      configurable: true,
      get: () => 640,
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
      configurable: true,
      get: () => 800,
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(function (callback) {
      callback(new Blob(["jpeg"], { type: "image/jpeg" }));
    });
  });

  it("shows the guide overlay, captures, previews, retakes and uses the photo", async () => {
    const stream = fakeStream();
    setCamera(() => Promise.resolve(stream));
    const state = newPhotosState();
    start(state);
    const user = userEvent.setup();
    await toFirstStep(user);
    expect(screen.getByTestId("photo-upload-button")).toBeInTheDocument(); // always offered
    await user.click(screen.getByTestId("photo-camera-button"));
    expect(await screen.findByTestId("camera-view")).toBeInTheDocument();
    expect(screen.getByTestId("camera-guide")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("camera-capture-button")).toBeEnabled());
    expect(screen.getByTestId("photo-upload-button")).toBeInTheDocument();

    await user.click(screen.getByTestId("camera-capture-button"));
    expect(await screen.findByTestId("camera-preview")).toBeInTheDocument();
    await user.click(screen.getByTestId("camera-retake-button"));
    expect(await screen.findByTestId("camera-view")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("camera-capture-button")).toBeEnabled());
    await user.click(screen.getByTestId("camera-capture-button"));
    await user.click(await screen.findByTestId("camera-use-button"));

    await waitFor(() => expect(state.uploads).toHaveLength(1));
    expect(state.uploads[0]).toEqual({
      angle: "front",
      fileName: "front-camera.jpg",
      captureMethod: "camera",
    });
    await waitFor(() =>
      expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Left 3/4"),
    );
    expect(stream.getTracks()[0].stop).toHaveBeenCalled();
  });

  it("offers upload, with a message and no camera view, when access is denied", async () => {
    setCamera(() => Promise.reject(new DOMException("denied", "NotAllowedError")));
    start(newPhotosState());
    const user = userEvent.setup();
    await toFirstStep(user);
    await user.click(screen.getByTestId("photo-camera-button"));
    expect(await screen.findByTestId("camera-error")).toHaveTextContent(
      "Camera access was not allowed. You can upload a photo instead",
    );
    expect(screen.queryByTestId("camera-video")).toBeNull();
    expect(screen.getByTestId("photo-upload-button")).toBeEnabled();
    await user.click(screen.getByTestId("camera-close-button"));
    expect(screen.queryByTestId("camera-error")).toBeNull();
  });

  it("says when no camera is found", async () => {
    setCamera(() => Promise.reject(new DOMException("none", "NotFoundError")));
    start(newPhotosState());
    const user = userEvent.setup();
    await toFirstStep(user);
    await user.click(screen.getByTestId("photo-camera-button"));
    expect(await screen.findByTestId("camera-error")).toHaveTextContent(
      "We couldn't find a camera on this device.",
    );
  });

  it("does not offer the camera at all when the browser has none", async () => {
    setCamera(undefined);
    start(newPhotosState());
    await toFirstStep(userEvent.setup());
    expect(screen.queryByTestId("photo-camera-button")).toBeNull();
    expect(screen.getByTestId("photo-upload-button")).toBeInTheDocument();
  });
});

describe("Review and the same-person gate (US5.11)", () => {
  it("opens on review for a complete set and continues only when clicked", async () => {
    start(withPhotos(newPhotosState(), { front: "a", left_3q: "a", right_3q: "a" }));
    expect(await screen.findByTestId("photo-review")).toBeInTheDocument();
    const continueButton = screen.getByTestId("review-continue-button");
    expect(continueButton).toBeEnabled();
    expect(router.push).not.toHaveBeenCalled();
    await userEvent.setup().click(continueButton);
    expect(router.push).toHaveBeenCalledWith("/payment");
    expect(toastMock.success).toHaveBeenCalledWith("Your photos are saved.");
  });

  it("highlights the flagged photo with text and an icon and disables Continue with its reason", async () => {
    start(withPhotos(newPhotosState(), { front: "a", left_3q: "b", right_3q: "a" }));
    const flagged = await screen.findByTestId("review-photo-left_3q");
    expect(flagged).toHaveAttribute("data-flagged", "true");
    expect(screen.getByTestId("review-flag-left_3q")).toHaveTextContent(
      "Needs a retake: These photos don't appear to show the same person. Please retake this photo in the same light and position as the others.",
    );
    expect(screen.getByTestId("review-photo-front")).toHaveAttribute("data-flagged", "false");
    const continueButton = screen.getByTestId("review-continue-button");
    expect(continueButton).toBeDisabled();
    expect(screen.getByTestId("review-continue-reason")).toHaveTextContent(
      "Retake the highlighted photo to continue.",
    );
    expect(continueButton).toHaveAccessibleDescription("Retake the highlighted photo to continue.");
  });

  it("flags both sides when all three differ, keeping front", async () => {
    start(withPhotos(newPhotosState(), { front: "a", left_3q: "b", right_3q: "c" }));
    await screen.findByTestId("photo-review");
    expect(screen.getByTestId("review-photo-front")).toHaveAttribute("data-flagged", "false");
    expect(screen.getByTestId("review-photo-left_3q")).toHaveAttribute("data-flagged", "true");
    expect(screen.getByTestId("review-photo-right_3q")).toHaveAttribute("data-flagged", "true");
  });

  it("a retake that fixes the set returns to review without navigating on its own", async () => {
    const state = withPhotos(newPhotosState(), { front: "a", left_3q: "b", right_3q: "a" });
    start(state);
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("review-retake-left_3q"));
    expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Left 3/4");
    expect(screen.getByTestId("photo-current")).toBeInTheDocument();
    state.hold = true;
    await uploadAs(user, "person-a-left.png");
    expect(await screen.findByTestId("photo-checking")).toBeInTheDocument();
    act(() => state.release());
    expect(await screen.findByTestId("photo-review")).toBeInTheDocument();
    expect(screen.getByTestId("review-continue-button")).toBeEnabled();
    expect(router.push).not.toHaveBeenCalled(); // AC5.11.4: stays until clicked
  });

  it("a retake that only moves the flag keeps Continue disabled", async () => {
    // Flip-flop B ([IV] §4): A/A/B, retake right as B -> front flagged.
    const state = withPhotos(newPhotosState(), { front: "a", left_3q: "b", right_3q: "a" });
    start(state);
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("review-retake-right_3q"));
    await uploadAs(user, "person-b-right.png");
    expect(await screen.findByTestId("photo-review")).toBeInTheDocument();
    expect(screen.getByTestId("review-photo-front")).toHaveAttribute("data-flagged", "true");
    expect(screen.getByTestId("review-continue-button")).toBeDisabled();
    expect(router.push).not.toHaveBeenCalled();
  });

  it("goes back to review from a retake step without uploading", async () => {
    start(withPhotos(newPhotosState(), { front: "a", left_3q: "a", right_3q: "a" }));
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("review-retake-front"));
    expect(screen.getByTestId("photo-back-button")).toHaveTextContent("Back to review");
    await user.click(screen.getByTestId("photo-back-button"));
    expect(await screen.findByTestId("photo-review")).toBeInTheDocument();
  });

  it("steps back through the angles to the rules", async () => {
    start(withPhotos(newPhotosState(), { front: "a" }));
    const user = userEvent.setup();
    await toFirstStep(user);
    expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Left 3/4");
    await user.click(screen.getByTestId("photo-back-button"));
    expect(screen.getByTestId("photo-step-title")).toHaveTextContent("Front");
    expect(screen.getByTestId("photo-back-button")).toHaveTextContent("Back to the rules");
    await user.click(screen.getByTestId("photo-back-button"));
    expect(screen.getByTestId("photo-requirements")).toBeInTheDocument();
  });
});
