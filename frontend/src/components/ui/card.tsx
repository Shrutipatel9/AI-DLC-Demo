import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// Cards: border only, no shadow, one corner radius (design-system-mapping §3).
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius)] border border-card-border bg-card p-6 sm:p-8",
        className,
      )}
      {...props}
    />
  );
}
