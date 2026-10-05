// Photo helpers: the API functions, the set rules the screens rely on, the file preflight and
// the camera wrappers (US5.2, US5.3, US5.6, US5.11; AC5.2.3, AC5.2.6, AC5.3.2, AC5.11.3).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import {
  TEST_REQUIREMENTS,
  newPhotosState,
  photoSet,
  withPhotos,
} from "@/test-utils/photos-server";

import {
  CameraError,
  UPLOAD_TIMEOUT_MS,
  cameraSupported,
  captureFrame,
  continueState,
  entryFor,
  fileProblem,
  flaggedAngles,
  getPhotoSet,
  getRequirements,
  isComplete,
  loadPhoto,
  megabytes,
  nextAngle,
  openCamera,
  progressText,
  stopCamera,
  uploadPhoto,
} from ".";

beforeEach(() => {
  configureApiOrigin("http://api.test");
});

describe("photo API functions", () => {
  it("reads the requirements and the set through the single API client", async () => {
    const empty = photoSet(newPhotosState());
    const requests = mockFetch(
      route("GET", "/photos/requirements", () => jsonResponse(200, TEST_REQUIREMENTS)),
      route("GET", "/photos", () => jsonResponse(200, empty)),
    );
    expect(await getRequirements()).toEqual(TEST_REQUIREMENTS);
    expect(await getPhotoSet()).toEqual(empty);
    expect(requests.every((r) => r.credentials === "include")).toBe(true);
    expect(requests.every((r) => r.headers["x-requested-with"] === "XMLHttpRequest")).toBe(true);
  });

  it("uploads multipart with the capture method and a longer timeout", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const requests = mockFetch(
      route("PUT", "/photos/left_3q", () => jsonResponse(200, photoSet(newPhotosState()))),
    );
    await uploadPhoto("left_3q", new Blob(["x"]), "left.jpg", "camera");
    const form = requests[0].rawBody as FormData;
    expect((form.get("file") as File).name).toBe("left.jpg");
    expect(form.get("captureMethod")).toBe("camera");
    expect(UPLOAD_TIMEOUT_MS).toBe(60_000);
    vi.useRealTimers();
  });

  it("reads a private photo as a Blob", async () => {
    mockFetch(route("GET", "/media/file-1", () => new Response("png", { status: 200 })));
    const blob = await loadPhoto("/media/file-1");
    expect(await blob.text()).toBe("png");
  });
});

describe("photo set rules", () => {
  const complete = () =>
    photoSet(withPhotos(newPhotosState(), { front: "a", left_3q: "a", right_3q: "a" }));

  it("counts progress against the configured angles", () => {
    expect(progressText(photoSet(newPhotosState()))).toBe("0 of 3");
    expect(progressText(photoSet(withPhotos(newPhotosState(), { front: "a" })))).toBe("1 of 3");
  });

  it("finds the next angle to take, wrapping around after the given one", () => {
    const set = photoSet(withPhotos(newPhotosState(), { left_3q: "a" }));
    expect(nextAngle(set)).toBe("front");
    expect(nextAngle(set, "front")).toBe("right_3q");
    expect(nextAngle(set, "right_3q")).toBe("front");
    expect(nextAngle(complete())).toBeNull();
    expect(isComplete(complete())).toBe(true);
  });

  it("reads an angle that is absent from the set as missing", () => {
    expect(entryFor({ ...complete(), photos: [] }, "front")).toEqual({
      angle: "front",
      status: "missing",
      reasons: [],
      imageUrl: null,
    });
  });

  it("treats a pending result as not consistent (AC5.11.3)", () => {
    expect(continueState(complete(), null)).toEqual({ enabled: false, reason: "pending" });
  });

  it("enables Continue only for a complete, consistent set", () => {
    const set = complete();
    expect(continueState(set, set.identity)).toEqual({ enabled: true });
    expect(continueState(set, { status: "mismatch", mismatchedAngles: ["front"] })).toEqual({
      enabled: false,
      reason: "mismatch",
    });
    const partial = photoSet(withPhotos(newPhotosState(), { front: "a" }));
    expect(continueState(partial, partial.identity)).toEqual({
      enabled: false,
      reason: "incomplete",
    });
  });

  it("only a mismatch has flagged angles", () => {
    expect(flaggedAngles(null)).toEqual([]);
    expect(flaggedAngles({ status: "consistent", mismatchedAngles: [] })).toEqual([]);
    expect(flaggedAngles({ status: "mismatch", mismatchedAngles: ["left_3q"] })).toEqual([
      "left_3q",
    ]);
  });
});

describe("file preflight (AC5.2.3)", () => {
  const MAX = 10 * 1024 * 1024;
  const file = (name: string, type: string, size = 10) =>
    new File([new Uint8Array(size)], name, { type });

  it("accepts JPEG, PNG and HEIC by type or extension", () => {
    expect(fileProblem(file("a.jpg", "image/jpeg"), MAX)).toBeNull();
    expect(fileProblem(file("a.png", "image/png"), MAX)).toBeNull();
    expect(fileProblem(file("IMG.HEIC", ""), MAX)).toBeNull();
    expect(fileProblem(file("photo", "image/heif"), MAX)).toBeNull();
  });

  it("refuses other types, empty files and files over the limit", () => {
    expect(fileProblem(file("a.gif", "image/gif"), MAX)).toBe("type");
    expect(fileProblem(file("a.dng", "image/x-adobe-dng"), MAX)).toBe("type");
    expect(fileProblem(file("a.png", "image/png", 0), MAX)).toBe("empty");
    expect(fileProblem(file("a.png", "image/png", 2048), 1024)).toBe("size");
    expect(megabytes(MAX)).toBe(10);
    expect(megabytes(10)).toBe(1);
  });
});

describe("camera wrappers (US5.3)", () => {
  afterEach(() => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
  });

  function camera(getUserMedia: () => Promise<MediaStream>) {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn(getUserMedia) },
    });
  }

  it("is unavailable without mediaDevices", async () => {
    expect(cameraSupported()).toBe(false);
    await expect(openCamera()).rejects.toMatchObject({ problem: "unavailable" });
  });

  it("opens the front camera without audio", async () => {
    const stream = {} as MediaStream;
    camera(() => Promise.resolve(stream));
    expect(cameraSupported()).toBe(true);
    await expect(openCamera()).resolves.toBe(stream);
    const call = vi.mocked(navigator.mediaDevices.getUserMedia).mock.calls[0][0];
    expect(call).toMatchObject({ audio: false, video: { facingMode: "user" } });
  });

  it.each([
    ["NotAllowedError", "denied"],
    ["SecurityError", "denied"],
    ["NotFoundError", "unavailable"],
    ["OverconstrainedError", "unavailable"],
    ["AbortError", "failed"],
  ])("maps %s to %s", async (name, problem) => {
    camera(() => Promise.reject(new DOMException("x", name)));
    const error = await openCamera().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(CameraError);
    expect((error as CameraError).problem).toBe(problem);
  });

  it("stops every track", () => {
    const tracks = [{ stop: vi.fn() }, { stop: vi.fn() }];
    stopCamera({ getTracks: () => tracks } as unknown as MediaStream);
    stopCamera(null);
    expect(tracks.every((track) => track.stop.mock.calls.length === 1)).toBe(true);
  });

  it("refuses to capture before the video has a size", async () => {
    const video = document.createElement("video");
    await expect(captureFrame(video)).rejects.toMatchObject({ problem: "failed" });
  });
});
