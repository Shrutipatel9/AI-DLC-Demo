// A small, stateful stand-in for the /photos and /media API (contract C1), used with
// `mockFetch` in component tests. It mirrors the server rules the UI relies on: one current
// photo per angle, a rejection keeps an accepted photo, and the same-person result is
// recomputed from the current photos on every answer. Test-only module.
//
// The uploaded file's NAME picks the outcome: "reject-<REASON>[-<REASON>]..." is rejected with
// those reasons; "person-<x>" is accepted as person x (default "a"). Photos of different
// people at the default three angles produce the documented flags.
import type { components } from "@/lib/api/types.gen";

import { errorResponse, jsonResponse, type RecordedRequest } from "./fetch-mock";

type Requirements = components["schemas"]["PhotoRequirements"];
type PhotoSet = components["schemas"]["PhotoSet"];
type PhotoOut = components["schemas"]["PhotoOut"];

export const ANGLES = ["front", "left_3q", "right_3q"];

export const TEST_REQUIREMENTS: Requirements = {
  catalogVersion: "photos-test",
  rules: [
    { id: "no_glasses_hat", text: "No glasses or hat" },
    { id: "even_light", text: "Natural, even light" },
    { id: "white_background", text: "Plain white background" },
    { id: "hair_back", text: "Hair tied back" },
    { id: "no_makeup", text: "No makeup" },
    { id: "no_neck_cover", text: "No clothing covering your neck" },
    { id: "no_filters", text: "No filters" },
  ],
  guidance: ["Look straight at the camera", "Keep a neutral expression"],
  angles: [
    {
      id: "front",
      label: "Front",
      instruction: "Face the camera head-on.",
      turnHint: "Look straight at the camera.",
      illustration: "front",
    },
    {
      id: "left_3q",
      label: "Left 3/4",
      instruction: "Turn your head to your right, about 45 degrees.",
      turnHint: "Turn your head to your right so your left cheek faces the camera.",
      illustration: "left",
    },
    {
      id: "right_3q",
      label: "Right 3/4",
      instruction: "Turn your head to your left, about 45 degrees.",
      turnHint: "Turn your head to your left so your right cheek faces the camera.",
      illustration: "right",
    },
  ],
  maxUploadBytes: 10 * 1024 * 1024,
  acceptedTypes: ["image/jpeg", "image/png", "image/heic"],
};

interface Stored {
  status: "accepted" | "rejected";
  person?: string;
  reasons: string[];
  fileId?: string;
  captureMethod?: "upload" | "camera";
}

export interface PhotosServerState {
  submitted: boolean;
  photos: Map<string, Stored>;
  uploads: { angle: string; fileName: string; captureMethod: string | null }[];
  /** Hold every upload answer until `release()` is called (to test the pending state). */
  hold: boolean;
  release: () => void;
  nextFileId: number;
}

export function newPhotosState(options: Partial<Pick<PhotosServerState, "submitted">> = {}) {
  const state: PhotosServerState = {
    submitted: options.submitted ?? true,
    photos: new Map(),
    uploads: [],
    hold: false,
    release: () => undefined,
    nextFileId: 1,
  };
  return state;
}

/** Pre-store accepted photos, e.g. `{ front: "a", left_3q: "b", right_3q: "a" }`. */
export function withPhotos(state: PhotosServerState, people: Record<string, string>) {
  for (const [angle, person] of Object.entries(people)) {
    state.photos.set(angle, {
      status: "accepted",
      person,
      reasons: [],
      fileId: `file-${state.nextFileId++}`,
    });
  }
  return state;
}

/** The match-count vote of [IV] §3 for exactly three angles (front kept when none agree). */
function identity(state: PhotosServerState): PhotoSet["identity"] {
  const people = ANGLES.map((angle) => state.photos.get(angle));
  if (people.some((photo) => photo?.status !== "accepted")) {
    return { status: "incomplete", mismatchedAngles: [] };
  }
  const [front, left, right] = people.map((photo) => photo?.person);
  if (front === left && left === right) return { status: "consistent", mismatchedAngles: [] };
  if (front === left) return { status: "mismatch", mismatchedAngles: ["right_3q"] };
  if (front === right) return { status: "mismatch", mismatchedAngles: ["left_3q"] };
  if (left === right) return { status: "mismatch", mismatchedAngles: ["front"] };
  return { status: "mismatch", mismatchedAngles: ["left_3q", "right_3q"] };
}

export function photoSet(state: PhotosServerState): PhotoSet {
  const photos: PhotoOut[] = ANGLES.map((angle) => {
    const stored = state.photos.get(angle);
    if (!stored) return { angle, status: "missing", reasons: [], imageUrl: null };
    return {
      angle,
      status: stored.status,
      reasons: stored.status === "rejected" ? stored.reasons : [],
      imageUrl: stored.fileId ? `/media/${stored.fileId}` : null,
      captureMethod: stored.captureMethod ?? null,
    };
  });
  return {
    requiredAngles: ANGLES,
    acceptedCount: photos.filter((photo) => photo.status === "accepted").length,
    photos,
    identity: identity(state),
  };
}

function path(request: RecordedRequest): string {
  return new URL(request.url, "http://x").pathname;
}

async function handleUpload(state: PhotosServerState, angle: string, body: FormData) {
  const file = body.get("file");
  const fileName = file instanceof File ? file.name : "blob";
  const captureMethod = body.get("captureMethod");
  state.uploads.push({
    angle,
    fileName,
    captureMethod: typeof captureMethod === "string" ? captureMethod : null,
  });
  if (state.hold) {
    await new Promise<void>((resolve) => {
      state.release = resolve;
    });
  }
  const rejected = /^reject-([A-Z_-]+)/.exec(fileName);
  if (rejected) {
    const reasons = rejected[1].split("-").filter(Boolean);
    const current = state.photos.get(angle);
    if (current?.status !== "accepted") state.photos.set(angle, { status: "rejected", reasons });
    return errorResponse(422, "PHOTO_REJECTED", {
      details: reasons.map((reason) => ({ angle, reason })),
    });
  }
  const person = /person-([a-z])/.exec(fileName)?.[1] ?? "a";
  state.photos.set(angle, {
    status: "accepted",
    person,
    reasons: [],
    fileId: `file-${state.nextFileId++}`,
    captureMethod: captureMethod === "camera" ? "camera" : "upload",
  });
  return jsonResponse(200, photoSet(state));
}

/** The fetch handler for mockFetch. */
export function photosServer(state: PhotosServerState) {
  return (request: RecordedRequest): Response | Promise<Response> | undefined => {
    const url = path(request);
    if (url.startsWith("/media/") && request.method === "GET") {
      return new Response(new Uint8Array([137, 80, 78, 71]), {
        status: 200,
        headers: { "Content-Type": "image/png" },
      });
    }
    if (!url.startsWith("/photos")) return undefined;
    if (!state.submitted) return errorResponse(409, "QUESTIONNAIRE_NOT_SUBMITTED");
    if (url === "/photos/requirements") return jsonResponse(200, TEST_REQUIREMENTS);
    if (url === "/photos" && request.method === "GET") return jsonResponse(200, photoSet(state));
    const angle = url.split("/").at(-1) ?? "";
    if (request.method === "PUT" && ANGLES.includes(angle) && request.rawBody instanceof FormData) {
      return handleUpload(state, angle, request.rawBody);
    }
    return errorResponse(404, "NOT_FOUND");
  };
}
