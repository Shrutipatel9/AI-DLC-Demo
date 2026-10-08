// A small, scripted stand-in for the /images API and the private /media bytes, used with
// `mockFetch` in component tests. `reads` are answered in order by GET /images (the last one
// repeats), so a test can script "generating, generating, settled" the way the worker would.
// Test-only module.
import type { components } from "@/lib/api/types.gen";

import { errorResponse, jsonResponse, type RecordedRequest } from "./fetch-mock";

export type Images = components["schemas"]["ImagesOut"];
export type Slot = components["schemas"]["ImageSlotOut"];

const AI_LABEL = "AI-generated illustration";
const FEATURES = [
  "hair",
  "eyebrows",
  "eyes",
  "nose",
  "cheeks",
  "jaw",
  "lips",
  "chin",
  "skin",
  "neck",
  "ears",
];

function slot(slotId: string, group: Slot["group"], title: string, overrides: Partial<Slot>): Slot {
  return {
    slotId,
    group,
    title,
    status: "ready",
    imageUrl: `/media/${slotId}`,
    aiLabel: AI_LABEL,
    retriesLeft: 3,
    ...overrides,
  };
}

/** The 24 slots in report order; `overrides` changes single slots by id. */
export function makeSlots(overrides: Record<string, Partial<Slot>> = {}): Slot[] {
  const all: [string, Slot["group"], string][] = [
    ...FEATURES.map((key): [string, Slot["group"], string] => [key, "feature", key]),
    ...[1, 2, 3, 4, 5].map((n): [string, Slot["group"], string] => [
      `hairstyle_${n}`,
      "hairstyle",
      `Hairstyle ${n}`,
    ]),
    ...[1, 2, 3, 4, 5].map((n): [string, Slot["group"], string] => [
      `outfit_${n}`,
      "outfit",
      `Outfit ${n}`,
    ]),
    ["aging_plus_3", "aging", "In 3 years"],
    ["aging_plus_5", "aging", "In 5 years"],
    ["aging_plus_10", "aging", "In 10 years"],
  ];
  const changes = new Map(Object.entries(overrides));
  return all.map(([id, group, title]) => slot(id, group, title, changes.get(id) ?? {}));
}

export function makeImages(
  overrides: Record<string, Partial<Slot>> = {},
  extra: Partial<Images> = {},
): Images {
  return {
    runId: "11111111-1111-4111-8111-111111111111",
    generating: false,
    frontPhotoUrl: "/media/front",
    slots: makeSlots(overrides),
    ...extra,
  };
}

/** A slot that is not available yet. */
export function unavailable(retriesLeft = 3): Partial<Slot> {
  return { status: "not_available", imageUrl: null, retriesLeft };
}

/** A slot that is still being created. */
export const GENERATING_SLOT: Partial<Slot> = { status: "generating", imageUrl: null };

type RetryAnswer = Slot | { status: number; code: string };

export interface ImagesServerState {
  /** Answers of GET /images in order; empty means 404 (no run). */
  reads: Images[];
  /** What POST /images/{slotId}/retry answers. */
  retry: RetryAnswer;
  retries: string[];
  failReads: boolean;
}

export function newImagesState(overrides: Partial<ImagesServerState> = {}): ImagesServerState {
  return {
    reads: [makeImages()],
    retry: makeSlots()[0],
    retries: [],
    failReads: false,
    ...overrides,
  };
}

/** A `mockFetch` handler serving GET /images, POST /images/{slotId}/retry and /media/*. */
export function imagesServer(state: ImagesServerState) {
  return (request: RecordedRequest): Response | undefined => {
    const path = new URL(request.url, "http://x").pathname;
    if (path.startsWith("/media/") && request.method === "GET") {
      return new Response(new Uint8Array([137, 80, 78, 71]), {
        status: 200,
        headers: { "Content-Type": "image/png" },
      });
    }
    if (request.method === "GET" && path === "/images") {
      if (state.failReads) return errorResponse(500, "INTERNAL_ERROR");
      if (state.reads.length === 0) return errorResponse(404, "NOT_FOUND");
      const next = state.reads.length > 1 ? state.reads.shift()! : state.reads[0];
      return jsonResponse(200, next);
    }
    const retry = /^\/images\/([^/]+)\/retry$/.exec(path);
    if (request.method === "POST" && retry) {
      state.retries.push(decodeURIComponent(retry[1]));
      return "slotId" in state.retry
        ? jsonResponse(200, state.retry)
        : errorResponse(state.retry.status, state.retry.code);
    }
    return undefined;
  };
}
