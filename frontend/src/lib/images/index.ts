// The only AI-images entry point for UI code (FE-004: UI never imports the API client).
export {
  getImages,
  loadImage,
  retryImage,
  type ImageSlot,
  type ImagesState,
  type SlotGroup,
} from "./api";
export { POLL_INTERVAL_MS, useVisuals, type Visuals, type VisualsPhase } from "./visuals";
