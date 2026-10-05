"use client";

// One question per screen (US4.2; interaction-spec §6 QuestionStep). The input follows the
// question type from the definition: free text, single choice (radio group), multi-select
// (checkbox group, grouped under headings) or Yes/No. A follow-up revealed by the answer
// (for example "Yes" -> "Please list your medications") appears inline and is announced.
import { forwardRef, type ReactNode } from "react";

import { describedBy, FieldError } from "@/components/ui/form-field";
import { followUpVisible, type DraftAnswer, type Question } from "@/lib/onboarding";

const FIELD_CLASS =
  "block w-full rounded-[var(--radius)] border border-input-border bg-white px-3 py-2 text-base text-foreground placeholder:text-muted aria-[invalid=true]:border-danger";
const LONG_TEXT = 500;

interface QuestionStepProps {
  question: Question;
  draft: DraftAnswer;
  error?: string;
  onChange: (draft: DraftAnswer) => void;
}

function Choice({
  type,
  name,
  checked,
  onChange,
  label,
  testId,
}: {
  type: "radio" | "checkbox";
  name: string;
  checked: boolean;
  onChange: () => void;
  label: string;
  testId: string;
}) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-[var(--radius)] border border-card-border px-3 text-base text-heading has-[:checked]:border-accent-strong">
      <input
        type={type}
        name={name}
        checked={checked}
        onChange={onChange}
        className="size-5 accent-[var(--accent-strong)]"
        data-testid={testId}
      />
      <span>{label}</span>
    </label>
  );
}

function TextAnswer({
  id,
  value,
  maxLength,
  placeholder,
  invalid,
  describedById,
  testId,
  onChange,
}: {
  id: string;
  value: string;
  maxLength: number;
  placeholder?: string | null;
  invalid: boolean;
  describedById?: string;
  testId: string;
  onChange: (value: string) => void;
}) {
  const shared = {
    id,
    value,
    maxLength,
    placeholder: placeholder ?? undefined,
    "aria-invalid": invalid ? ("true" as const) : ("false" as const),
    "aria-describedby": [describedById, `${id}-count`].filter(Boolean).join(" "),
    "data-testid": testId,
    className: FIELD_CLASS,
  };
  return (
    <>
      {maxLength > LONG_TEXT ? (
        <textarea rows={4} {...shared} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input
          type="text"
          {...shared}
          className={`${FIELD_CLASS} min-h-11`}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      <p id={`${id}-count`} className="mt-1 text-sm text-muted">
        {value.length} / {maxLength} characters
      </p>
    </>
  );
}

function ChoiceList({ question, draft, onChange }: Omit<QuestionStepProps, "error">) {
  const name = `answer-${question.id}`;
  if (question.type === "yesno") {
    return (
      <div className="space-y-2" role="radiogroup" aria-labelledby={`${question.id}-legend`}>
        {[true, false].map((option) => (
          <Choice
            key={String(option)}
            type="radio"
            name={name}
            checked={draft.value === option}
            onChange={() => onChange({ ...draft, value: option })}
            label={option ? "Yes" : "No"}
            testId={option ? "question-yes" : "question-no"}
          />
        ))}
      </div>
    );
  }
  const options = question.options ?? [];
  if (question.type === "single") {
    return (
      <div className="space-y-2" role="radiogroup" aria-labelledby={`${question.id}-legend`}>
        {options.map((option) => (
          <Choice
            key={option.value}
            type="radio"
            name={name}
            checked={draft.value === option.value}
            onChange={() => onChange({ ...draft, value: option.value })}
            label={option.label}
            testId={`question-option-${option.value}`}
          />
        ))}
      </div>
    );
  }
  const selected = Array.isArray(draft.value) ? draft.value : [];
  const groups: { name: string | null; items: typeof options }[] = [];
  for (const option of options) {
    const group = option.group ?? null;
    const last = groups.at(-1);
    if (last && last.name === group) last.items.push(option);
    else groups.push({ name: group, items: [option] });
  }
  const toggle = (value: string) =>
    onChange({
      ...draft,
      value: selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value],
    });
  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <div key={group.name ?? "options"} role="group" aria-label={group.name ?? undefined}>
          {group.name ? (
            <p className="mb-2 text-base font-semibold text-heading">{group.name}</p>
          ) : null}
          <div className="space-y-2">
            {group.items.map((option) => (
              <Choice
                key={option.value}
                type="checkbox"
                name={name}
                checked={selected.includes(option.value)}
                onChange={() => toggle(option.value)}
                label={option.label}
                testId={`question-option-${option.value}`}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/** The question card. The legend receives focus when a new question appears. */
export const QuestionStep = forwardRef<HTMLHeadingElement, QuestionStepProps>(function QuestionStep(
  { question, draft, error, onChange },
  legendRef,
) {
  const errorId = describedBy("question", { error: Boolean(error) });
  const followUp = question.followUp;
  const showFollowUp = followUpVisible(question, draft.value);
  let input: ReactNode;
  if (question.type === "text") {
    input = (
      <TextAnswer
        id="question-text"
        value={typeof draft.value === "string" ? draft.value : ""}
        maxLength={question.maxLength ?? LONG_TEXT}
        placeholder={question.placeholder}
        invalid={Boolean(error)}
        describedById={errorId}
        testId="question-text-input"
        onChange={(value) => onChange({ ...draft, value })}
      />
    );
  } else {
    input = <ChoiceList question={question} draft={draft} onChange={onChange} />;
  }
  return (
    <fieldset
      className="space-y-4"
      aria-describedby={errorId}
      aria-invalid={error ? "true" : undefined}
      data-testid="question-step"
    >
      <legend className="w-full">
        <h2
          id={`${question.id}-legend`}
          ref={legendRef}
          tabIndex={-1}
          className="text-xl font-semibold text-heading outline-none"
          data-testid="question-legend"
        >
          {question.type === "text" ? (
            <label htmlFor="question-text">{question.text}</label>
          ) : (
            question.text
          )}
        </h2>
        {question.required ? null : <p className="mt-1 text-sm text-muted">Optional</p>}
      </legend>
      {input}
      <div aria-live="polite">
        {showFollowUp && followUp ? (
          <div className="space-y-1 pt-2" data-testid="question-follow-up">
            <label htmlFor="question-follow-up" className="block font-medium text-heading">
              {followUp.label} <span className="text-sm text-muted">(optional)</span>
            </label>
            <TextAnswer
              id="question-follow-up"
              value={draft.followUpText}
              maxLength={followUp.maxLength}
              invalid={false}
              testId="question-follow-up-input"
              onChange={(followUpText) => onChange({ ...draft, followUpText })}
            />
          </div>
        ) : null}
      </div>
      <FieldError id="question" message={error} />
    </fieldset>
  );
});
