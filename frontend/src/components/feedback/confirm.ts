// `confirm()` — the shared confirmation for destructive actions (US11.7; BR3.2, BR7.3).
//
// It opens the single ConfirmDialogHost and resolves to true (confirmed) or false
// (cancelled, Escape). The opener (the element that had focus) gets focus back on close.
// `confirmLabel` is required and must name the action ("Log out", "Delete photo"), never a
// generic "OK" (NFD post-review R-05).
import { useSyncExternalStore } from "react";

export interface ConfirmOptions {
  title: string;
  body: string;
  /** Names the action, for example "Log out". Generic labels are refused. */
  confirmLabel: string;
  cancelLabel?: string;
}

export interface ConfirmRequest extends ConfirmOptions {
  id: number;
}

interface Pending extends ConfirmRequest {
  resolve(value: boolean): void;
  opener: HTMLElement | null;
}

const GENERIC_LABELS = /^(ok|okay|yes|confirm|continue|submit)$/i;

let pending: Pending | null = null;
let nextId = 1;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Ask the user to confirm a destructive action. */
export function confirm(options: ConfirmOptions): Promise<boolean> {
  if (!options.confirmLabel.trim() || GENERIC_LABELS.test(options.confirmLabel.trim())) {
    throw new Error("confirm() needs a confirm label that names the action");
  }
  pending?.resolve(false);
  const opener =
    typeof document === "undefined" ? null : (document.activeElement as HTMLElement | null);
  return new Promise<boolean>((resolve) => {
    pending = { ...options, id: nextId++, resolve, opener };
    emit();
  });
}

/** Close the open dialog with the user's answer and return focus to the opener. */
export function settleConfirm(value: boolean): void {
  const current = pending;
  if (!current) return;
  pending = null;
  emit();
  current.resolve(value);
  current.opener?.focus();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot(): ConfirmRequest | null {
  return pending;
}

/** The open request, for ConfirmDialogHost. */
export function useConfirmRequest(): ConfirmRequest | null {
  return useSyncExternalStore(subscribe, snapshot, () => null);
}
