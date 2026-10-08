// Plain-language text for the AI Visuals screen (US9.2-US9.5).
export const AI_LABEL = "AI-generated illustration";

export const VISUALS_TITLE = "Your AI Visuals";
export const VISUALS_INTRO =
  "Every picture here, except your own photo, is an AI-generated illustration. It shows an idea of a look, not a promise or a prediction.";

export const GENERATING_ANNOUNCEMENT = "Your images are still being created.";
export const SETTLED_ANNOUNCEMENT = "Your images are ready.";

export const NOT_AVAILABLE_TEXT = "Not available yet";
export const RETRY_SUCCESS = "Your image is ready.";
export const RETRY_FAILURE = "We couldn't create that image. Please try again.";

/** Help text under the retry button. */
export function retriesLeftText(retriesLeft: number): string {
  if (retriesLeft <= 0) return "No retries left for this image.";
  return retriesLeft === 1 ? "1 retry left." : `${retriesLeft} retries left.`;
}
