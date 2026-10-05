// In-browser camera capture (US5.3). Thin wrappers over getUserMedia and a canvas, so the
// screens can be tested with a mocked camera (granted, denied or absent).

export type CameraProblem = "denied" | "unavailable" | "failed";

export class CameraError extends Error {
  readonly problem: CameraProblem;

  constructor(problem: CameraProblem) {
    super(`camera ${problem}`);
    this.name = "CameraError";
    this.problem = problem;
  }
}

/** True when the browser can ask for a camera at all (AC5.3.2: otherwise only upload). */
export function cameraSupported(): boolean {
  return (
    typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getUserMedia === "function"
  );
}

/** Open the front camera; throws CameraError("denied" | "unavailable" | "failed"). */
export async function openCamera(): Promise<MediaStream> {
  if (!cameraSupported()) throw new CameraError("unavailable");
  try {
    return await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 1600 } },
      audio: false,
    });
  } catch (error) {
    // DOMException is not an Error subclass in every engine: read the name from any object.
    const name =
      typeof error === "object" && error !== null && "name" in error ? String(error.name) : "";
    if (name === "NotAllowedError" || name === "SecurityError") throw new CameraError("denied");
    if (name === "NotFoundError" || name === "OverconstrainedError") {
      throw new CameraError("unavailable");
    }
    throw new CameraError("failed");
  }
}

export function stopCamera(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop());
}

/**
 * Take one frame as a JPEG. The frame is NOT mirrored, even though the live view is shown
 * mirrored, so the stored photo turns the way the person really turned.
 */
export function captureFrame(video: HTMLVideoElement): Promise<Blob> {
  const width = video.videoWidth;
  const height = video.videoHeight;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context || width === 0 || height === 0) {
    return Promise.reject(new CameraError("failed"));
  }
  context.drawImage(video, 0, 0, width, height);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new CameraError("failed"))),
      "image/jpeg",
      0.92,
    );
  });
}
