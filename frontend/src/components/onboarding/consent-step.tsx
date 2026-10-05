"use client";

// Consent before the questionnaire (US4.1; AC4.1.1, AC4.1.2; mockups §3.1). The text and
// its version come from configuration; Continue stays disabled until the box is ticked,
// with the reason shown next to it.
import { useId, useState } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { isApiError } from "@/lib/api/errors";
import { giveConsent, type ConsentState } from "@/lib/onboarding";

import { CONSENT_CHANGED, onboardingMessage } from "./messages";

export function ConsentStep({
  consent,
  onConsented,
  onTextChanged,
}: {
  consent: ConsentState;
  onConsented: () => void;
  onTextChanged: () => void;
}) {
  const [agreed, setAgreed] = useState(false);
  const [saving, setSaving] = useState(false);
  const reasonId = useId();
  const [heading, ...lines] = consent.consentText.split("\n").filter((line) => line.trim());

  async function onContinue() {
    setSaving(true);
    try {
      await giveConsent(consent.consentTextVersion);
      toast.success("Thank you. Your consent is saved.");
      onConsented();
    } catch (error) {
      if (!isApiError(error)) throw error;
      setSaving(false);
      if (error.code === "CONSENT_REQUIRED") {
        toast.error(CONSENT_CHANGED);
        onTextChanged();
        return;
      }
      toast.error(onboardingMessage(error));
    }
  }

  return (
    <section aria-labelledby="consent-heading" data-testid="consent-step">
      <h1 id="consent-heading" className="text-2xl font-bold text-heading">
        Before we start
      </h1>
      <div className="mt-4 space-y-2 text-base text-foreground" data-testid="consent-text">
        {heading ? <h2 className="text-lg font-semibold text-heading">{heading}</h2> : null}
        <ul className="list-disc space-y-1 pl-6">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
      <label className="mt-6 flex items-start gap-3 text-base text-heading">
        <input
          type="checkbox"
          className="mt-1 size-5 accent-[var(--accent-strong)]"
          checked={agreed}
          onChange={(event) => setAgreed(event.target.checked)}
          aria-describedby={agreed ? undefined : reasonId}
          data-testid="consent-checkbox"
        />
        <span>{consent.agreementText}</span>
      </label>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button
          type="button"
          disabled={!agreed || saving}
          onClick={() => void onContinue()}
          data-testid="consent-continue-button"
        >
          {saving ? "Saving…" : "Continue"}
        </Button>
        {agreed ? null : (
          <p id={reasonId} className="text-sm text-muted" data-testid="consent-reason">
            Tick the box to continue.
          </p>
        )}
      </div>
    </section>
  );
}
