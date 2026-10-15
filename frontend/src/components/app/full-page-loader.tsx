"use client";

import { WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";

import { PageLoader } from "./page-loader";

// Shown on protected pages while the session is restored (BR6.1): never the login form.
// When the server cannot be reached (network error or 5xx) it offers Retry (BR6.5).
export function FullPageLoader({ failed, onRetry }: { failed: boolean; onRetry: () => void }) {
  if (failed) {
    return (
      <main id="main" className="mx-auto max-w-[480px] px-4 py-20 text-center">
        <span
          aria-hidden="true"
          className="mx-auto mb-5 inline-flex size-16 items-center justify-center rounded-2xl bg-surface-muted text-subheading"
        >
          <WifiOff className="size-8" />
        </span>
        <p role="alert" className="text-base text-heading" data-testid="session-restore-error">
          We couldn&apos;t reach the server. Check your connection and try again.
        </p>
        <Button className="mt-6" onClick={onRetry} data-testid="session-retry-button">
          Retry
        </Button>
      </main>
    );
  }
  return (
    <main id="main">
      <PageLoader message="Restoring your session" testId="session-loader" />
    </main>
  );
}
