"use client";

import { RefreshCw, ServerCrash } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { isApiError } from "@/lib/api/errors";

/** The request id of a failed API call, when the error came from the API client. */
export function requestIdOf(error: unknown): string | null {
  return isApiError(error) ? error.requestId : null;
}

// Error boundary view (NFR5.11, AC1.8.2): logs the failing call's request id to the console
// (no third-party error tracking yet) and shows it in small text.
export function ErrorView({ error, reset }: { error: Error; reset: () => void }) {
  const requestId = requestIdOf(error);
  useEffect(() => {
    console.error("Unhandled UI error", { requestId, name: error.name });
  }, [error, requestId]);
  return (
    <main id="main" className="mx-auto max-w-[480px] px-4 py-20 text-center">
      <span
        aria-hidden="true"
        className="mx-auto mb-5 inline-flex size-16 items-center justify-center rounded-2xl bg-danger-soft text-danger"
      >
        <ServerCrash className="size-8" />
      </span>
      <h1 className="text-2xl font-bold text-heading">
        Something went wrong on our side. Please try again.
      </h1>
      {requestId ? (
        <p className="mt-2 text-sm text-muted" data-testid="error-request-id">
          Reference: {requestId}
        </p>
      ) : null}
      <Button className="mt-6" onClick={reset} data-testid="error-try-again-button">
        <RefreshCw aria-hidden="true" />
        Try again
      </Button>
    </main>
  );
}
