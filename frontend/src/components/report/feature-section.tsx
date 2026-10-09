// One of the 11 feature sections (US8.4, US8.7): the narrative, my photo next to the AI "after"
// image (always labelled and described as an AI illustration), projected-potential ideas, a
// metrics table that scrolls inside its own area, and a summary callout.
import { ImageOff, ScanFace } from "lucide-react";

import { PhotoThumbnail } from "@/components/photos/photo-thumbnail";
import type { ReportFeature } from "@/lib/report";

import { CREATING_TEXT, NOT_AVAILABLE_TEXT } from "./messages";

function Placeholder({ text, testId }: { text: string; testId: string }) {
  return (
    <div
      className="flex aspect-[4/5] w-full flex-col items-center justify-center gap-2 rounded-ui border border-card-border bg-white p-3 text-center"
      data-testid={testId}
    >
      <ImageOff className="h-6 w-6 text-muted" aria-hidden="true" />
      <p className="text-sm font-medium text-heading">{text}</p>
    </div>
  );
}

function Metrics({ feature }: { feature: ReportFeature }) {
  if (feature.metrics.length === 0) {
    return (
      <p className="text-base text-muted" data-testid={`metrics-none-${feature.key}`}>
        {feature.noMeasurementReason}
      </p>
    );
  }
  return (
    // Scrolls sideways inside its own box so the page never does (AC8.4.3); focusable so a
    // keyboard user can scroll it.
    <div
      role="region"
      tabIndex={0}
      aria-label={`${feature.title} measurements`}
      className="overflow-x-auto"
      data-testid={`metrics-${feature.key}`}
    >
      <table className="w-full min-w-[22rem] text-left text-base">
        <thead>
          <tr>
            <th scope="col" className="bg-surface-muted px-3 py-2 font-semibold first:rounded-l-lg">
              Measurement
            </th>
            <th scope="col" className="bg-surface-muted px-3 py-2 font-semibold first:rounded-l-lg">
              Value
            </th>
            <th scope="col" className="rounded-r-lg bg-surface-muted px-3 py-2 font-semibold">
              Unit
            </th>
          </tr>
        </thead>
        <tbody>
          {feature.metrics.map((metric) => (
            <tr key={metric.name} className="border-t border-card-border">
              <th scope="row" className="px-3 py-2 font-normal">
                {metric.label}
              </th>
              <td className="px-3 py-2 font-semibold text-heading">{metric.value}</td>
              <td className="px-3 py-2 text-subheading">{metric.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FeatureSection({ feature }: { feature: ReportFeature }) {
  const { after } = feature;
  return (
    <section
      aria-labelledby={`section-${feature.key}`}
      className="space-y-4 rounded-card border border-card-border bg-white p-5 shadow-card sm:p-6"
      data-testid={`feature-${feature.key}`}
    >
      <h3
        id={`section-${feature.key}`}
        tabIndex={-1}
        className="flex items-center gap-2.5 text-xl font-bold text-heading"
      >
        <span
          aria-hidden="true"
          className="inline-flex size-8 items-center justify-center rounded-lg bg-accent-soft text-accent-strong"
        >
          <ScanFace className="size-[18px]" />
        </span>
        {feature.title}
      </h3>
      <p className="text-base text-heading">{feature.narrative}</p>

      <div className="grid max-w-xl grid-cols-2 gap-4">
        <figure>
          {feature.beforeImageUrl ? (
            <PhotoThumbnail
              imageUrl={feature.beforeImageUrl}
              alt={feature.beforeAlt}
              testId={`feature-before-${feature.key}`}
            />
          ) : (
            <Placeholder text={NOT_AVAILABLE_TEXT} testId={`feature-before-${feature.key}`} />
          )}
          <figcaption className="mt-2 text-sm font-medium text-heading">Your photo</figcaption>
        </figure>
        <figure>
          {after.status === "ready" && after.imageUrl ? (
            <PhotoThumbnail
              imageUrl={after.imageUrl}
              alt={after.alt}
              testId={`feature-after-${feature.key}`}
            />
          ) : (
            <Placeholder
              text={after.status === "pending" ? CREATING_TEXT : NOT_AVAILABLE_TEXT}
              testId={`feature-after-${feature.key}`}
            />
          )}
          <figcaption className="mt-2 text-sm font-medium text-heading">
            After
            {after.status === "ready" ? (
              <span
                className="ml-2 inline-block rounded-full bg-surface-muted px-2 py-1 text-xs"
                data-testid={`feature-ai-label-${feature.key}`}
              >
                {after.aiLabel}
              </span>
            ) : null}
          </figcaption>
        </figure>
      </div>

      {feature.potentialIdeas.length > 0 ? (
        <div>
          <h4 className="text-base font-semibold text-heading">Projected potential</h4>
          <ul className="mt-1 list-disc space-y-1 pl-6 text-base">
            {feature.potentialIdeas.map((idea) => (
              <li key={idea}>{idea}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div>
        <h4 className="mb-1 text-base font-semibold text-heading">Measurements</h4>
        <Metrics feature={feature} />
      </div>

      {feature.subSections.map((sub) => (
        <div key={sub.heading} data-testid={`subsection-${feature.key}`}>
          <h4 className="text-base font-semibold text-heading">{sub.heading}</h4>
          <p className="mt-1 text-base">{sub.body}</p>
        </div>
      ))}

      {feature.summary ? (
        <aside
          className="rounded-ui border-l-4 border-accent-strong bg-accent-soft p-4"
          data-testid={`feature-summary-${feature.key}`}
        >
          <h4 className="text-base font-semibold text-heading">{feature.title} Summary</h4>
          <p className="mt-1 text-base">{feature.summary}</p>
        </aside>
      ) : null}
    </section>
  );
}
