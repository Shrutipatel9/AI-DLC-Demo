// Photo endpoints (contract C1 /photos, /media; US5.1, US5.2, US5.5, US5.6). UI code never
// imports the API client (FE-004); it calls these functions through `@/lib/photos`.
import { apiBlob, apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

type Schemas = components["schemas"];

export type PhotoRequirements = Schemas["PhotoRequirements"];
export type AngleInfo = Schemas["AngleOut"];
export type PhotoRule = Schemas["PhotoRuleOut"];
export type PhotoSet = Schemas["PhotoSet"];
export type PhotoEntry = Schemas["PhotoOut"];
export type IdentityResult = Schemas["IdentityOut"];
export type CaptureMethod = "upload" | "camera";

/** Uploads can be up to 10 MB and are checked on the server: allow a minute. */
export const UPLOAD_TIMEOUT_MS = 60_000;

export function getRequirements(): Promise<PhotoRequirements> {
  return apiRequest<PhotoRequirements>("/photos/requirements");
}

export function getPhotoSet(): Promise<PhotoSet> {
  return apiRequest<PhotoSet>("/photos");
}

/** Upload or replace one angle's photo; the answer is the whole set, identity recomputed. */
export function uploadPhoto(
  angle: string,
  file: Blob,
  fileName: string,
  captureMethod: CaptureMethod,
): Promise<PhotoSet> {
  const form = new FormData();
  form.append("file", file, fileName);
  form.append("captureMethod", captureMethod);
  return apiRequest<PhotoSet>(`/photos/${encodeURIComponent(angle)}`, {
    method: "PUT",
    body: form,
    timeoutMs: UPLOAD_TIMEOUT_MS,
  });
}

/** Read a private photo (`imageUrl` from the set) with the access token, as a Blob. */
export function loadPhoto(imageUrl: string): Promise<Blob> {
  return apiBlob(imageUrl);
}
