import { Camera, Check, ClipboardList, CreditCard, FileText, ScanFace } from "lucide-react";

import { cn } from "@/lib/utils";

export const JOURNEY_STEPS = [
  { key: "questionnaire", label: "Questionnaire", icon: ClipboardList },
  { key: "photos", label: "Photos", icon: Camera },
  { key: "payment", label: "Payment", icon: CreditCard },
  { key: "analysis", label: "Analysis", icon: ScanFace },
  { key: "report", label: "Report", icon: FileText },
] as const;

export type JourneyStepKey = (typeof JOURNEY_STEPS)[number]["key"];

/**
 * Where the user is in the journey: questionnaire -> photos -> payment -> analysis -> report.
 * Purely informative; each page still decides what the user may do.
 */
export function JourneySteps({
  current,
  className,
}: {
  current: JourneyStepKey;
  className?: string;
}) {
  const currentIndex = JOURNEY_STEPS.findIndex((step) => step.key === current);
  return (
    <nav aria-label="Your progress" className={cn("mb-8", className)} data-testid="journey-steps">
      <ol className="flex items-center gap-1 sm:gap-2">
        {JOURNEY_STEPS.map(({ key, label, icon: Icon }, index) => {
          const done = index < currentIndex;
          const active = index === currentIndex;
          return (
            <li key={key} className="flex flex-1 items-center gap-1 sm:gap-2 last:flex-none">
              <span
                aria-current={active ? "step" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-full py-1 pl-1 pr-1 text-sm font-semibold sm:pr-3",
                  active && "bg-white text-accent-deep shadow-card ring-1 ring-accent-soft-border",
                  done && "text-success",
                  !active && !done && "text-muted",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "inline-flex size-8 items-center justify-center rounded-full [&_svg]:size-4",
                    active && "bg-brand-gradient text-white",
                    done && "bg-success-soft text-success",
                    !active && !done && "bg-surface-muted text-muted",
                  )}
                >
                  {done ? <Check /> : <Icon />}
                </span>
                <span className={active ? "" : "hidden md:inline"}>
                  {label}
                  {done ? <span className="sr-only"> (done)</span> : null}
                </span>
              </span>
              {index < JOURNEY_STEPS.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "h-0.5 flex-1 rounded-full",
                    done ? "bg-success/40" : "bg-card-border",
                  )}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
