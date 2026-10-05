import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// Inputs are at least 16 px (no iOS zoom) with a 3:1 border (design-system-mapping §4).
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "block min-h-11 w-full rounded-[var(--radius)] border border-input-border bg-white px-3 text-base text-foreground placeholder:text-muted aria-[invalid=true]:border-danger",
        className,
      )}
      {...props}
    />
  );
}
