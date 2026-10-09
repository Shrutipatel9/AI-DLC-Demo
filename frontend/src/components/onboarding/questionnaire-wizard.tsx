"use client";

// The one-question-per-screen questionnaire (US4.2-US4.4; plan decision D6; mockups §3.2-3.3).
//
// - Shows "Question N of M"; M follows branching (the server recalculates the visible
//   questions after every save, AC4.2.1-AC4.2.3).
// - Next saves the answer (AC4.2.6); Back keeps earlier answers editable (AC4.2.5).
// - The last visible question carries the disclaimer and Submit (AC4.3.1-AC4.3.4).
// - Resumes at the first unanswered visible question.
import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { isApiError, type ApiError } from "@/lib/api/errors";
import {
  emptyValue,
  isAnswered,
  resumeIndex,
  saveAnswer,
  submitQuestionnaire,
  valueToSave,
  type DraftAnswer,
  type QuestionnaireDefinition,
  type QuestionnaireProgress,
} from "@/lib/onboarding";

import { DisclaimerGate, SupportPanel } from "./disclaimer-gate";
import { CHOOSE_ANSWER, ENTER_ANSWER, onboardingMessage, SAVE_FAILED } from "./messages";
import { QuestionStep } from "./question-step";

function initialDrafts(progress: QuestionnaireProgress): ReadonlyMap<string, DraftAnswer> {
  return new Map(
    Object.entries(progress.answers).map(([id, answer]) => [
      id,
      { value: answer.value, followUpText: answer.followUpText ?? "" },
    ]),
  );
}

export function QuestionnaireWizard({
  definition,
  initialProgress,
  onSubmitted,
  onConsentRequired,
}: {
  definition: QuestionnaireDefinition;
  initialProgress: QuestionnaireProgress;
  onSubmitted: () => void;
  onConsentRequired: () => void;
}) {
  const [progress, setProgress] = useState(initialProgress);
  const [index, setIndex] = useState(() =>
    resumeIndex(initialProgress.visibleQuestionIds, initialProgress.answers),
  );
  const [drafts, setDrafts] = useState(() => initialDrafts(initialProgress));
  const [error, setError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [cannotConfirm, setCannotConfirm] = useState(false);
  const legendRef = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);
  const reasonId = useId();

  const byId = useMemo(
    () => new Map(definition.questions.map((question) => [question.id, question])),
    [definition],
  );
  const visible = progress.visibleQuestionIds;
  const question = byId.get(visible.at(index) ?? "");
  const isLast = index === visible.length - 1;

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    legendRef.current?.focus();
  }, [index]);

  if (!question) return null;
  const current = question;
  const draft = drafts.get(current.id) ?? { value: emptyValue(current), followUpText: "" };

  function failed(failure: ApiError) {
    if (failure.code === "CONSENT_REQUIRED") {
      toast.error(onboardingMessage(failure));
      onConsentRequired();
      return;
    }
    if (failure.code === "VALIDATION_FAILED") setError(onboardingMessage(failure));
    toast.error(failure.code === "VALIDATION_FAILED" ? SAVE_FAILED : onboardingMessage(failure));
  }

  async function saveCurrent(): Promise<QuestionnaireProgress | null> {
    const value = valueToSave(current, draft.value);
    if (!isAnswered(current, draft.value) || value === null) {
      setError(current.type === "text" ? ENTER_ANSWER : CHOOSE_ANSWER);
      legendRef.current?.focus();
      return null;
    }
    const saved = await saveAnswer(current.id, value, draft.followUpText.trim() || null);
    setProgress(saved);
    return saved;
  }

  async function onNext(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError(undefined);
    setBusy(true);
    try {
      const saved = await saveCurrent();
      if (!saved) return;
      const position = saved.visibleQuestionIds.indexOf(current.id);
      setIndex(Math.min(position + 1, saved.visibleQuestionIds.length - 1));
    } catch (failure) {
      if (!isApiError(failure)) throw failure;
      failed(failure);
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit() {
    if (busy || !confirmed) return;
    setError(undefined);
    setBusy(true);
    try {
      const saved = await saveCurrent();
      if (!saved) return;
      await submitQuestionnaire(true);
      toast.success("Thank you. Your answers are submitted.");
      onSubmitted();
    } catch (failure) {
      if (!isApiError(failure)) throw failure;
      const missing = failure.details.find((detail) => detail.reason === "REQUIRED")?.field;
      if (failure.code === "VALIDATION_FAILED" && missing && visible.includes(missing)) {
        setIndex(visible.indexOf(missing));
        setError(CHOOSE_ANSWER);
        toast.error("Please answer every question before submitting.");
        return;
      }
      failed(failure);
    } finally {
      setBusy(false);
    }
  }

  if (cannotConfirm) {
    return (
      <SupportPanel supportUrl={definition.supportUrl} onBack={() => setCannotConfirm(false)} />
    );
  }

  const total = visible.length;
  return (
    <form noValidate onSubmit={(event) => void onNext(event)} data-testid="questionnaire-wizard">
      <div className="mb-6">
        <div className="flex items-center justify-between text-sm font-semibold">
          <p className="text-subheading" data-testid="wizard-position">
            Question {index + 1} of {total}
          </p>
          <span aria-hidden="true" className="text-accent-strong">
            {Math.round(((index + 1) / total) * 100)}%
          </span>
        </div>
        <div
          role="progressbar"
          aria-label={`Question ${index + 1} of ${total}`}
          aria-valuemin={1}
          aria-valuemax={total}
          aria-valuenow={index + 1}
          className="mt-2.5 h-2.5 w-full overflow-hidden rounded-full bg-surface-muted"
          data-testid="wizard-progress"
        >
          <div
            className="h-full rounded-full bg-brand-gradient transition-[width] duration-500"
            style={{ width: `${Math.round(((index + 1) / total) * 100)}%` }}
          />
        </div>
      </div>
      <QuestionStep
        key={current.id}
        ref={legendRef}
        question={current}
        draft={draft}
        error={error}
        onChange={(next) => {
          setDrafts((all) => new Map(all).set(current.id, next));
          setError(undefined);
        }}
      />
      {isLast ? (
        <DisclaimerGate
          text={definition.disclaimerText}
          checked={confirmed}
          onCheckedChange={setConfirmed}
          reasonId={reasonId}
        />
      ) : null}
      <div className="sticky bottom-0 mt-8 flex gap-3 border-t border-card-border bg-card py-3 sm:static sm:justify-between sm:pt-6 sm:pb-0">
        <Button
          type="button"
          variant="secondary"
          className="flex-1 sm:flex-none"
          disabled={index === 0 || busy}
          onClick={() => {
            setError(undefined);
            setIndex((value) => Math.max(value - 1, 0));
          }}
          data-testid="wizard-back-button"
        >
          Back
        </Button>
        {isLast ? (
          <Button
            type="button"
            className="flex-1 sm:flex-none"
            disabled={!confirmed || busy}
            aria-describedby={confirmed ? undefined : reasonId}
            onClick={() => void onSubmit()}
            data-testid="wizard-submit-button"
          >
            {busy ? "Submitting…" : "Submit"}
          </Button>
        ) : (
          <Button
            type="submit"
            className="flex-1 sm:flex-none"
            disabled={busy}
            data-testid="wizard-next-button"
          >
            {busy ? "Saving…" : "Next"}
          </Button>
        )}
      </div>
      {isLast ? (
        <div className="mt-3 space-y-2">
          {confirmed ? null : (
            <p id={reasonId} className="text-sm text-muted" data-testid="disclaimer-reason">
              Please confirm the statement above to submit.
            </p>
          )}
          <Button
            type="button"
            variant="link"
            onClick={() => setCannotConfirm(true)}
            data-testid="disclaimer-cannot-confirm-link"
          >
            I can&apos;t confirm this statement
          </Button>
        </div>
      ) : null}
    </form>
  );
}
