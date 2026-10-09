import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Label } from "./label";

// Label above the input, hint and error below, wired with aria-describedby (FormField spec).
export function FormField({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint ? (
        <div id={`${id}-hint`} className="text-sm text-muted">
          {hint}
        </div>
      ) : null}
      <FieldError id={id} message={error} />
    </div>
  );
}

/**
 * Inline field error (BR7.4, AC11.7.4): text next to the field, linked to it through the
 * input's `aria-describedby` (see `describedBy`) with `aria-invalid` set on the input. A toast
 * may add context, but this message is always present.
 */
export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p
      id={`${id}-error`}
      className="flex items-start gap-1.5 text-sm font-medium text-danger"
      data-testid={`${id}-error`}
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </p>
  );
}

/** Build the aria-describedby value for a field. */
export function describedBy(
  id: string,
  options: { hint?: boolean; error?: boolean },
): string | undefined {
  const ids = [options.hint ? `${id}-hint` : null, options.error ? `${id}-error` : null].filter(
    Boolean,
  );
  return ids.length ? ids.join(" ") : undefined;
}
