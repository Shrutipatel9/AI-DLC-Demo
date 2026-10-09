"use client";

// A private photo shown from a Blob: the image is read with the access token through the API
// client (it is never a public URL, AC1.10.2) and its object URL is revoked on unmount.
import { ImageOff } from "lucide-react";
import { useEffect, useState } from "react";

import { loadPhoto } from "@/lib/photos";
import { cn } from "@/lib/utils";

export function PhotoThumbnail({
  imageUrl,
  alt,
  className,
  testId,
}: {
  imageUrl: string;
  alt: string;
  className?: string;
  testId?: string;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let created: string | null = null;
    loadPhoto(imageUrl)
      .then((blob) => {
        if (!active) return;
        created = URL.createObjectURL(blob);
        setObjectUrl(created);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [imageUrl]);

  const frame = cn(
    "flex aspect-[4/5] w-full items-center justify-center overflow-hidden rounded-ui border border-card-border bg-white",
    className,
  );
  if (failed) {
    return (
      <div className={frame} data-testid={testId} data-state="failed">
        <ImageOff className="h-6 w-6 text-muted" aria-hidden="true" />
        <span className="sr-only">{alt} (could not be shown)</span>
      </div>
    );
  }
  if (!objectUrl) {
    return <div className={cn(frame, "animate-pulse")} data-testid={testId} data-state="loading" />;
  }
  return (
    <div className={frame} data-testid={testId} data-state="loaded">
      {/* eslint-disable-next-line @next/next/no-img-element -- a private blob: URL; next/image cannot optimise it */}
      <img src={objectUrl} alt={alt} className="h-full w-full object-contain" />
    </div>
  );
}
