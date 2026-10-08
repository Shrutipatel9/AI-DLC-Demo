"use client";

// The AI Visuals screen (US9.2-US9.5): five hairstyles, five outfits and the four-card aging
// stack (the user's own front photo first, then +3, +5 and +10 years). Every generated image
// carries the "AI-generated illustration" label (AC9.2.1, AC9.3.1, AC9.4.1). An image that is
// not available yet offers a retry button (AC9.5.2); a failed retry shows an error toast and
// the slot stays marked (AC9.5.3); after three retries the button is disabled (AC9.5.4). While
// images are generating the screen polls and says so politely; nothing here blocks the report.
import { ImageOff } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { toast } from "@/components/feedback/toast";
import { PhotoThumbnail } from "@/components/photos/photo-thumbnail";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useVisuals, type ImageSlot, type SlotGroup } from "@/lib/images";

import {
  AI_LABEL,
  GENERATING_ANNOUNCEMENT,
  NOT_AVAILABLE_TEXT,
  RETRY_FAILURE,
  RETRY_SUCCESS,
  SETTLED_ANNOUNCEMENT,
  VISUALS_INTRO,
  VISUALS_TITLE,
  retriesLeftText,
} from "./messages";

const FRAME =
  "flex aspect-[4/5] w-full flex-col items-center justify-center gap-2 overflow-hidden rounded-[var(--radius)] border border-card-border bg-white p-3 text-center";

function AiBadge({ slotId }: { slotId: string }) {
  return (
    <span
      className="mt-2 inline-block rounded-full bg-[#eef2f5] px-2 py-1 text-xs font-medium text-heading"
      data-testid={`visual-ai-label-${slotId}`}
    >
      {AI_LABEL}
    </span>
  );
}

function SlotCard({
  slot,
  retrying,
  onRetry,
}: {
  slot: ImageSlot;
  retrying: boolean;
  onRetry: (slot: ImageSlot) => void;
}) {
  const busy = retrying || slot.status === "generating";
  let body: ReactNode;
  if (busy) {
    body = (
      <div
        className={`${FRAME} animate-pulse`}
        aria-busy="true"
        data-testid={`visual-busy-${slot.slotId}`}
      >
        <span className="text-sm text-muted">Creating…</span>
      </div>
    );
  } else if (slot.status === "ready" && slot.imageUrl) {
    body = (
      <PhotoThumbnail
        imageUrl={slot.imageUrl}
        alt={`${slot.title}: ${AI_LABEL}`}
        testId={`visual-image-${slot.slotId}`}
      />
    );
  } else {
    const exhausted = slot.retriesLeft <= 0;
    body = (
      <div className={FRAME} data-testid={`visual-unavailable-${slot.slotId}`}>
        <ImageOff className="h-6 w-6 text-muted" aria-hidden="true" />
        <p className="text-sm font-medium text-heading">{NOT_AVAILABLE_TEXT}</p>
        <Button
          variant="secondary"
          onClick={() => onRetry(slot)}
          disabled={exhausted}
          aria-describedby={`visual-retry-help-${slot.slotId}`}
          data-testid={`visual-retry-${slot.slotId}`}
        >
          Retry
        </Button>
        <p
          id={`visual-retry-help-${slot.slotId}`}
          className="text-xs text-muted"
          data-testid={`visual-retry-help-${slot.slotId}`}
        >
          {retriesLeftText(slot.retriesLeft)}
        </p>
      </div>
    );
  }
  return (
    <li data-testid={`visual-${slot.slotId}`} data-state={busy ? "generating" : slot.status}>
      {body}
      <p className="mt-2 text-sm font-medium text-heading">{slot.title}</p>
      {slot.status === "ready" && !busy ? <AiBadge slotId={slot.slotId} /> : null}
    </li>
  );
}

export function VisualsScreen({ pollIntervalMs }: { pollIntervalMs?: number }) {
  const { phase, images, reload, retry } = useVisuals(pollIntervalMs);
  const [retrying, setRetrying] = useState<ReadonlySet<string>>(new Set());

  async function onRetry(slot: ImageSlot) {
    setRetrying((current) => new Set(current).add(slot.slotId));
    const result = await retry(slot.slotId);
    setRetrying((current) => {
      const next = new Set(current);
      next.delete(slot.slotId);
      return next;
    });
    if (result?.status === "ready") toast.success(RETRY_SUCCESS);
    else toast.error(RETRY_FAILURE);
  }

  let body: ReactNode;
  if (phase === "loading") {
    body = (
      <p role="status" className="text-base text-muted" data-testid="visuals-loading">
        Loading your images…
      </p>
    );
  } else if (phase === "error") {
    body = (
      <div className="space-y-4" data-testid="visuals-error">
        <p role="alert" className="text-base text-heading">
          We couldn&apos;t load your images. Please try again.
        </p>
        <Button onClick={reload} data-testid="visuals-retry-button">
          Try again
        </Button>
      </div>
    );
  } else if (phase === "none" || images === null) {
    body = (
      <section className="space-y-4" data-testid="visuals-none">
        <h1 className="text-2xl font-bold text-heading">Your images appear after your analysis</h1>
        <Link
          href="/analysis"
          className="inline-flex min-h-11 items-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
          data-testid="visuals-analysis-link"
        >
          Go to your analysis
        </Link>
      </section>
    );
  } else {
    const inGroup = (group: SlotGroup) => images.slots.filter((slot) => slot.group === group);
    const cards = (group: SlotGroup) =>
      inGroup(group).map((slot) => (
        <SlotCard
          key={slot.slotId}
          slot={slot}
          retrying={retrying.has(slot.slotId)}
          onRetry={(item) => void onRetry(item)}
        />
      ));
    const section = (group: SlotGroup, heading: string) => (
      <section aria-labelledby={`visuals-${group}-heading`} data-testid={`visuals-${group}`}>
        <h2 id={`visuals-${group}-heading`} className="mb-3 text-xl font-semibold text-heading">
          {heading}
        </h2>
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">{cards(group)}</ul>
      </section>
    );
    body = (
      <div className="space-y-8" data-testid="visuals" data-generating={images.generating}>
        <div>
          <h1 className="text-2xl font-bold text-heading">{VISUALS_TITLE}</h1>
          <p className="mt-2 text-base text-muted" data-testid="visuals-intro">
            {VISUALS_INTRO}
          </p>
        </div>
        {section("hairstyle", "Hairstyles")}
        {section("outfit", "Outfits")}
        <section aria-labelledby="visuals-aging-heading" data-testid="visuals-aging">
          <h2 id="visuals-aging-heading" className="mb-3 text-xl font-semibold text-heading">
            Healthy-aging preview
          </h2>
          <ul className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <li data-testid="visual-aging-now">
              {images.frontPhotoUrl ? (
                <PhotoThumbnail
                  imageUrl={images.frontPhotoUrl}
                  alt="Your own front photo"
                  testId="visual-image-aging-now"
                />
              ) : (
                <div className={FRAME} />
              )}
              <p className="mt-2 text-sm font-medium text-heading">Now (your photo)</p>
            </li>
            {cards("aging")}
          </ul>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <Card className="p-4 sm:p-8">
        <p className="sr-only" role="status" aria-live="polite" data-testid="visuals-announcement">
          {images === null
            ? ""
            : images.generating
              ? GENERATING_ANNOUNCEMENT
              : SETTLED_ANNOUNCEMENT}
        </p>
        {body}
      </Card>
    </div>
  );
}
