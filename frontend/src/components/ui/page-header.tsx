import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A tinted rounded square holding one icon (feature lists, headers, stats). */
export function IconTile({
  icon: Icon,
  tone = "indigo",
  className,
}: {
  icon: LucideIcon;
  tone?: "indigo" | "teal" | "violet" | "amber" | "rose";
  className?: string;
}) {
  const tones = new Map<string, string>(
    Object.entries({
      indigo: "bg-accent-soft text-accent-strong",
      teal: "bg-[#e6fffb] text-[#0f766e]",
      violet: "bg-[#f3efff] text-[#6d28d9]",
      amber: "bg-[#fff6e0] text-[#92590a]",
      rose: "bg-[#fff0f3] text-[#be123c]",
    }),
  );
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-11 shrink-0 items-center justify-center rounded-xl [&_svg]:size-[22px]",
        tones.get(tone),
        className,
      )}
    >
      <Icon />
    </span>
  );
}

/** Page title block: an optional eyebrow and icon, the h1, a subtitle and right-side actions. */
export function PageHeader({
  icon,
  eyebrow,
  title,
  subtitle,
  actions,
  titleId,
  titleTestId,
  className,
}: {
  icon?: LucideIcon;
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  titleId?: string;
  titleTestId?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="flex items-start gap-4">
        {icon ? <IconTile icon={icon} className="mt-1 hidden sm:inline-flex" /> : null}
        <div>
          {eyebrow ? (
            <p className="mb-1 text-sm font-semibold uppercase tracking-wider text-accent-strong">
              {eyebrow}
            </p>
          ) : null}
          <h1
            id={titleId}
            className="text-3xl font-bold text-heading sm:text-[34px]"
            data-testid={titleTestId}
          >
            {title}
          </h1>
          {subtitle ? <p className="mt-2 max-w-2xl text-lg text-subheading">{subtitle}</p> : null}
        </div>
      </div>
      {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
    </div>
  );
}

/** A small pill label. */
export function Badge({
  children,
  tone = "indigo",
  className,
}: {
  children: ReactNode;
  tone?: "indigo" | "success" | "warning" | "neutral" | "danger";
  className?: string;
}) {
  const tones = new Map<string, string>(
    Object.entries({
      indigo: "border-accent-soft-border bg-accent-soft text-accent-deep",
      success: "border-[#abefc6] bg-success-soft text-success",
      warning: "border-[#fedf89] bg-[var(--warning-surface)] text-[var(--warning-text)]",
      neutral: "border-card-border bg-surface-muted text-subheading",
      danger: "border-[#fecdca] bg-danger-soft text-danger",
    }),
  );
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-sm font-semibold [&_svg]:size-3.5",
        tones.get(tone),
        className,
      )}
    >
      {children}
    </span>
  );
}
