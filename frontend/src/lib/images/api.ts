// AI image endpoints (U7; US9.1-US9.5). UI code never imports the API client (FE-004); it calls
// these functions through `@/lib/images`.
import { apiBlob, apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

export type ImagesState = components["schemas"]["ImagesOut"];
export type ImageSlot = components["schemas"]["ImageSlotOut"];
export type SlotGroup = ImageSlot["group"];

/** The current run's images and their state (404 NOT_FOUND when no analysis was started). */
export function getImages(): Promise<ImagesState> {
  return apiRequest<ImagesState>("/images");
}

/** One retry of an image that is not available yet (at most 3 per image). */
export function retryImage(slotId: string): Promise<ImageSlot> {
  return apiRequest<ImageSlot>(`/images/${encodeURIComponent(slotId)}/retry`, { method: "POST" });
}

/** Read a private image with the access token, as a Blob. */
export function loadImage(imageUrl: string): Promise<Blob> {
  return apiBlob(imageUrl);
}
