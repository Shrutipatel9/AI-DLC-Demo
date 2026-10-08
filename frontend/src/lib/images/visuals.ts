// Following the AI Visuals (US9.2-US9.5). The screen polls GET /images every few seconds while
// images are being generated, stops when they are all settled, and merges a manual retry's
// answer into the list.
//
// - `phase` is "loading" until the first answer, "none" when no analysis was started (404),
//   "error" when the first read failed, then "ready";
// - a failed poll after the first answer keeps the last known images and tries again.
import { useCallback, useEffect, useRef, useState } from "react";

import { isApiError } from "@/lib/api/errors";

import { getImages, retryImage, type ImageSlot, type ImagesState } from "./api";

export const POLL_INTERVAL_MS = 3_000;

export type VisualsPhase = "loading" | "none" | "error" | "ready";

export interface Visuals {
  phase: VisualsPhase;
  images: ImagesState | null;
  /** Read the images again now (the "Try again" button after a load error). */
  reload: () => void;
  /** One manual retry; resolves the slot's new state, or null when the server refused it. */
  retry: (slotId: string) => Promise<ImageSlot | null>;
}

interface State {
  phase: VisualsPhase;
  images: ImagesState | null;
}

export function useVisuals(intervalMs: number = POLL_INTERVAL_MS): Visuals {
  const [state, setState] = useState<State>({ phase: "loading", images: null });
  const [generation, setGeneration] = useState(0);
  const hasImages = useRef(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      let again = true;
      try {
        const images = await getImages();
        if (!active) return;
        hasImages.current = true;
        setState({ phase: "ready", images });
        again = images.generating;
      } catch (error) {
        if (!active) return;
        if (isApiError(error) && error.code === "NOT_FOUND") {
          setState({ phase: "none", images: null });
          again = false;
        } else if (!hasImages.current) {
          setState({ phase: "error", images: null });
          again = false;
        }
      }
      if (active && again) timer = setTimeout(() => void poll(), intervalMs);
    };
    void poll();

    return () => {
      active = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [intervalMs, generation]);

  const reload = useCallback(() => {
    setState({ phase: "loading", images: null });
    hasImages.current = false;
    setGeneration((value) => value + 1);
  }, []);

  const retry = useCallback(async (slotId: string) => {
    try {
      const slot = await retryImage(slotId);
      setState((current) =>
        current.images
          ? {
              ...current,
              images: {
                ...current.images,
                slots: current.images.slots.map((item) => (item.slotId === slotId ? slot : item)),
              },
            }
          : current,
      );
      return slot;
    } catch {
      // A refused retry (for example the limit was already used) changes the counts: read again.
      setGeneration((value) => value + 1);
      return null;
    }
  }, []);

  return { phase: state.phase, images: state.images, reload, retry };
}
