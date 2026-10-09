"use client";

import { WifiOff } from "lucide-react";

import { LogoMark } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";

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
    <main id="main" className="flex min-h-screen items-center justify-center">
      <div
        role="status"
        aria-live="polite"
        className="flex flex-col items-center gap-3"
        data-testid="session-loader"
      >
        <span
          aria-hidden="true"
          className="relative inline-flex size-16 items-center justify-center"
        >
          <span className="absolute inset-0 animate-spin rounded-full border-4 border-accent-soft border-t-accent-strong" />
          <LogoMark className="size-8" />
        </span>
        <span className="text-base font-medium text-subheading">Restoring your session</span>
      </div>
    </main>
  );
}
