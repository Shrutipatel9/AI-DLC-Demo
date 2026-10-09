"use client";

// The app-wide toast service (US11.7; BR7.1, BR7.2; NFR9.9), wrapping Sonner.
//
// - success: role="status" (polite), auto-dismisses after 5 s;
// - error: role="alert" (assertive), stays until dismissed;
// - neither moves focus; each has a close button reachable by Tab.
// Every action with a real success or failure outcome reports through `toast`, except the
// forgot-password request, which never reveals its outcome (BR4.1).
import { CircleAlert, CircleCheck } from "lucide-react";
import { toast as sonner } from "sonner";

export const SUCCESS_TOAST_MS = 5_000;

type Kind = "success" | "error";

function ToastCard({ id, kind, message }: { id: string | number; kind: Kind; message: string }) {
  const isError = kind === "error";
  return (
    <div
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      className={`flex w-[min(380px,calc(100vw-32px))] items-start gap-3 rounded-card border border-l-4 bg-white p-4 text-[15px] text-heading shadow-popover ${
        isError ? "border-danger/40 border-l-danger" : "border-card-border border-l-success"
      }`}
      data-testid={`toast-${kind}`}
    >
      {isError ? (
        <CircleAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden="true" />
      ) : (
        <CircleCheck className="mt-0.5 size-5 shrink-0 text-success" aria-hidden="true" />
      )}
      <p className="flex-1">{message}</p>
      <button
        type="button"
        className="toast-close -m-1 inline-flex min-h-8 min-w-8 items-center justify-center rounded-lg p-1 text-muted hover:bg-surface-muted hover:text-heading"
        aria-label="Dismiss notification"
        onClick={() => sonner.dismiss(id)}
        data-testid="toast-close-button"
      >
        <span aria-hidden="true" className="text-xl leading-none">
          ×
        </span>
      </button>
    </div>
  );
}

function show(kind: Kind, message: string): string | number {
  return sonner.custom((id) => <ToastCard id={id} kind={kind} message={message} />, {
    duration: kind === "success" ? SUCCESS_TOAST_MS : Number.POSITIVE_INFINITY,
  });
}

export const toast = {
  success: (message: string) => show("success", message),
  error: (message: string) => show("error", message),
};
