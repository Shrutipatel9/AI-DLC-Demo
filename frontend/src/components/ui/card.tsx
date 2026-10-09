import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// Cards: a hairline border, a soft shadow and the large radius.
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-card border border-card-border bg-card p-6 shadow-card sm:p-8",
        className,
      )}
      {...props}
    />
  );
}
