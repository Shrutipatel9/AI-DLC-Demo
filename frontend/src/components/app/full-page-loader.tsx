"use client";

import { Button } from "@/components/ui/button";

// Shown on protected pages while the session is restored (BR6.1): never the login form.
// When the server cannot be reached (network error or 5xx) it offers Retry (BR6.5).
export function FullPageLoader({ failed, onRetry }: { failed: boolean; onRetry: () => void }) {
  if (failed) {
    return (
      <main id="main" className="mx-auto max-w-[480px] px-4 py-16 text-center">
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
          className="size-10 animate-spin rounded-full border-4 border-card-border border-t-accent"
        />
        <span className="text-base text-muted">Restoring your session</span>
      </div>
    </main>
  );
}
