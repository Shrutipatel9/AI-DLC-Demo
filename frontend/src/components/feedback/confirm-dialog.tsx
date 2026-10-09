"use client";

// The single confirmation dialog instance (BR7.3; NFR9.9; WF-U2-9 step 2), driven by
// `confirm()`. Accessible modal: focus moves to Cancel (the safe default) on open, Tab and
// Shift+Tab cycle inside, Escape cancels, and focus returns to the opener on close.
import { useEffect, useRef, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";

import { settleConfirm, useConfirmRequest } from "./confirm";

export function ConfirmDialogHost() {
  const request = useConfirmRequest();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (request) cancelRef.current?.focus();
  }, [request]);

  if (!request) return null;

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      settleConfirm(false);
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>("button:not([disabled])");
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const titleId = `confirm-title-${request.id}`;
  const bodyId = `confirm-body-${request.id}`;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 backdrop-blur-sm">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        onKeyDown={onKeyDown}
        className="w-full max-w-[440px] rounded-card border border-card-border bg-white p-6 shadow-[0_24px_60px_-12px_rgb(15_23_42/0.35)] sm:p-7"
        data-testid="confirm-dialog"
      >
        <h2 id={titleId} className="text-xl font-bold text-heading">
          {request.title}
        </h2>
        <p id={bodyId} className="mt-2 text-base text-subheading">
          {request.body}
        </p>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button
            ref={cancelRef}
            type="button"
            variant="secondary"
            onClick={() => settleConfirm(false)}
            data-testid="confirm-dialog-cancel"
          >
            {request.cancelLabel ?? "Cancel"}
          </Button>
          <Button
            type="button"
            onClick={() => settleConfirm(true)}
            data-testid="confirm-dialog-confirm"
          >
            {request.confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
