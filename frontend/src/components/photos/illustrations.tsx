// Example illustrations for the photo rules and angles ([PC] §2).
// [Decided by delivery team] Simple drawings stand in for the reference product's example
// photos until the client supplies its own images; no real person is shown.
import {
  Ban,
  Glasses,
  Scissors,
  Shirt,
  Sparkles,
  Square,
  Sun,
  WandSparkles,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type Direction = "front" | "left" | "right";

/**
 * A head outline turned like the requested photo. "left" means the left cheek faces the
 * camera, so in the photo the nose points to the image's left (and "right" the opposite).
 */
export function AngleIllustration({
  direction,
  className,
  title,
}: {
  direction: Direction;
  className?: string;
  title?: string;
}) {
  const shift = direction === "front" ? 0 : direction === "left" ? -14 : 14;
  return (
    <svg
      viewBox="0 0 120 150"
      className={cn("text-heading", className)}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <ellipse
        cx={60}
        cy={68}
        rx={direction === "front" ? 40 : 34}
        ry={52}
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
      />
      <path
        d="M38 118 Q60 132 82 118 L86 148 L34 148 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
      />
      <circle cx={46 + shift} cy={58} r={4} fill="currentColor" />
      <circle cx={74 + shift} cy={58} r={4} fill="currentColor" />
      <path
        d={`M${60 + shift} 62 L${60 + shift * 1.6} 82 L${60 + shift} 84`}
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
        strokeLinecap="round"
      />
      <path
        d={`M${48 + shift} 98 Q${60 + shift} 104 ${72 + shift} 98`}
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
        strokeLinecap="round"
      />
    </svg>
  );
}

const RULE_ICONS = new Map<string, { icon: LucideIcon; crossed: boolean }>([
  ["no_glasses_hat", { icon: Glasses, crossed: true }],
  ["even_light", { icon: Sun, crossed: false }],
  ["white_background", { icon: Square, crossed: false }],
  ["hair_back", { icon: Scissors, crossed: false }],
  ["no_makeup", { icon: Sparkles, crossed: true }],
  ["no_neck_cover", { icon: Shirt, crossed: true }],
  ["no_filters", { icon: WandSparkles, crossed: true }],
]);

/** The example illustration for one requirement rule (AC5.1.1). */
export function RuleIllustration({ ruleId }: { ruleId: string }) {
  const entry = RULE_ICONS.get(ruleId) ?? { icon: Square, crossed: false };
  const Icon = entry.icon;
  return (
    <span
      className="relative inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--radius)] border border-card-border bg-white text-heading"
      aria-hidden="true"
      data-testid={`photo-rule-illustration-${ruleId}`}
    >
      <Icon className="h-7 w-7" />
      {entry.crossed ? <Ban className="absolute h-11 w-11 text-danger" strokeWidth={1.5} /> : null}
    </span>
  );
}
