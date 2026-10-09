"use client";

// The disclaimer under the last question (US4.3; [QS] §4; interaction-spec DisclaimerGate).
// Submit is disabled until the box is ticked, with the reason visible (AC4.3.1). "I can't
// confirm this statement" opens a calm, supportive panel in place, with focus on its
// heading (AC4.3.4). Its wording is a [Recommendation] awaiting client confirmation, and the
// professional-support link is shown only when configured: none is invented.
import { useEffect, useId, useRef } from "react";

import { Button } from "@/components/ui/button";

export function DisclaimerGate({
  text,
  checked,
  onCheckedChange,
  reasonId,
}: {
  text: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  reasonId: string;
}) {
  return (
    <div className="mt-6 border-t border-card-border pt-6" data-testid="disclaimer-gate">
      <label className="flex cursor-pointer items-start gap-3 rounded-ui border border-[#fedf89] bg-[var(--warning-surface)] p-4 text-base text-heading">
        <input
          type="checkbox"
          className="mt-1 size-5 shrink-0 accent-[var(--accent-strong)]"
          checked={checked}
          onChange={(event) => onCheckedChange(event.target.checked)}
          aria-describedby={checked ? undefined : reasonId}
          data-testid="disclaimer-checkbox"
        />
        <span data-testid="disclaimer-text">{text}</span>
      </label>
    </div>
  );
}

export function SupportPanel({
  supportUrl,
  onBack,
}: {
  supportUrl?: string | null;
  onBack: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const headingId = useId();
  useEffect(() => {
    headingRef.current?.focus();
  }, []);
  return (
    <section
      aria-labelledby={headingId}
      className="rounded-ui border border-card-border bg-white p-6"
      data-testid="support-panel"
    >
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className="text-xl font-semibold text-heading outline-none"
      >
        Thank you for being honest with us.
      </h2>
      <p className="mt-3 text-base text-foreground">
        This analysis focuses on appearance, so it isn&apos;t the right fit when appearance concerns
        feel difficult. If you&apos;d like support, a qualified professional can help.
      </p>
      {supportUrl ? (
        <p className="mt-3">
          <a
            href={supportUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-strong underline underline-offset-4"
            data-testid="support-panel-link"
          >
            Find professional support
          </a>
        </p>
      ) : null}
      <p className="mt-3 text-base text-foreground">Your answers are saved.</p>
      <Button
        type="button"
        variant="secondary"
        className="mt-4"
        onClick={onBack}
        data-testid="support-panel-back-button"
      >
        Back to the questionnaire
      </Button>
    </section>
  );
}
