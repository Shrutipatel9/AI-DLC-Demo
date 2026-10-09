import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// Inputs are at least 16 px (no iOS zoom) with a 3:1 border and a soft focus halo.
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "block min-h-11 w-full rounded-ui border border-input-border bg-white px-3.5 text-base text-foreground shadow-sm transition-shadow placeholder:text-muted focus:border-accent-strong focus:shadow-focus focus:outline-none focus-visible:outline-none aria-[invalid=true]:border-danger aria-[invalid=true]:focus:shadow-[0_0_0_4px_rgb(180_35_24/0.12)]",
        className,
      )}
      {...props}
    />
  );
}
