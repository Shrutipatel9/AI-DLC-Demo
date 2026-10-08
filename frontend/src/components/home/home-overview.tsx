"use client";

// Home Overview (US11.1, US11.3): shown once a report exists. Key stats, the before/potential
// pair, "Priority Features to Improve", the Treatment Protocol card (Phase 01), the six-axis
// radar chart with its text alternative, the report status and the PDF download.
import Link from "next/link";

import { PhotoThumbnail } from "@/components/photos/photo-thumbnail";
import { DownloadPdfButton } from "@/components/report/download-pdf-button";
import { Card } from "@/components/ui/card";
import type { Home } from "@/lib/report";

import { RadarChart } from "./radar-chart";

/** "1 min 12 s", "45 s" - the analysis time in words. */
export function durationText(seconds: number | null): string {
  if (seconds === null) return "Not recorded";
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest === 0 ? `${minutes} min` : `${minutes} min ${rest} s`;
}

function Stat({ label, value, testId }: { label: string; value: string; testId: string }) {
  return (
    <div className="rounded-[var(--radius)] border border-card-border bg-white p-4">
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-heading" data-testid={testId}>
        {value}
      </p>
    </div>
  );
}

function Chip({ children }: { children: string }) {
  return (
    <span className="absolute left-2 top-2 rounded bg-[#282828] px-2 py-1 text-xs font-bold uppercase text-white">
      {children}
    </span>
  );
}

export function HomeOverview({ home, name }: { home: Home; name: string }) {
  const { protocol } = home;
  return (
    <div className="space-y-6" data-testid="home-overview">
      <Card>
        <h1 className="text-2xl font-bold text-heading" data-testid="home-greeting">
          Hi, {name}
        </h1>
        <p className="mt-2 text-base text-muted" data-testid="home-status" aria-live="polite">
          Your report is ready.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/report"
            className="inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
            data-testid="home-report-link"
          >
            View my report
          </Link>
          <DownloadPdfButton testId="home-download-pdf" />
          <Link
            href="/visuals"
            className="inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] border border-card-border bg-white px-4 text-base font-semibold text-heading hover:bg-[#eef2f5]"
            data-testid="home-visuals-link"
          >
            AI Visuals
          </Link>
        </div>
      </Card>

      <section aria-label="Key stats" className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Overall score"
          value={home.overallScore === null ? "Not scored" : `${home.overallScore}/100`}
          testId="home-stat-score"
        />
        <Stat
          label="Evaluated"
          value={`${home.evaluatedPoints} points`}
          testId="home-stat-points"
        />
        <Stat
          label="Analysis time"
          value={durationText(home.analysisDurationSeconds)}
          testId="home-stat-time"
        />
      </section>

      <Card>
        <h2 className="text-xl font-semibold text-heading">Before and potential</h2>
        <div className="mt-3 grid max-w-xl grid-cols-2 gap-4" data-testid="home-before-potential">
          <figure className="relative">
            {home.beforeImageUrl ? (
              <PhotoThumbnail
                imageUrl={home.beforeImageUrl}
                alt="Your front photo"
                testId="home-before-image"
              />
            ) : null}
            <Chip>Before</Chip>
          </figure>
          <figure className="relative">
            {home.potentialImageUrl ? (
              <PhotoThumbnail
                imageUrl={home.potentialImageUrl}
                alt={`${home.aiLabel} — your potential`}
                testId="home-potential-image"
              />
            ) : (
              <div className="flex aspect-[4/5] w-full items-center justify-center rounded-[var(--radius)] border border-card-border bg-white p-3 text-center text-sm font-medium text-heading">
                Not available yet
              </div>
            )}
            <Chip>Potential</Chip>
          </figure>
        </div>
        <p className="mt-2 text-sm text-muted">
          {home.aiLabel}: the potential picture is an idea, not a promise.
        </p>
      </Card>

      <Card>
        <h2 className="text-xl font-semibold text-heading">Priority Features to Improve</h2>
        {home.priorityFeatures.length === 0 ? (
          <p className="mt-2 text-base text-muted">No feature could be scored from your photos.</p>
        ) : (
          <ul className="mt-3 space-y-4" data-testid="home-priorities">
            {home.priorityFeatures.map((feature) => (
              <li key={feature.key} data-testid={`home-priority-${feature.key}`}>
                <p className="text-base font-semibold text-heading">
                  {feature.title} · {feature.score}/100 · {feature.label}
                </p>
                <ul className="mt-1 list-disc pl-6 text-base">
                  {feature.attributes.map((attribute) => (
                    <li key={attribute.name}>
                      {attribute.name}: {attribute.value}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-xl font-semibold text-heading">Harmony Profile</h2>
          <RadarChart axes={home.harmonyProfile} />
        </Card>
        <Card data-testid="home-protocol">
          <h2 className="text-xl font-semibold text-heading">Treatment Protocol</h2>
          <p className="mt-2 text-sm font-bold uppercase text-accent-strong">
            {protocol.phaseLabel}
          </p>
          <p className="text-lg font-semibold text-heading">{protocol.title}</p>
          <p className="text-sm text-muted">{protocol.timing}</p>
          {protocol.actions.length > 0 ? (
            <ul
              className="mt-3 list-disc space-y-1 pl-6 text-base"
              data-testid="home-protocol-actions"
            >
              {protocol.actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          ) : null}
          <p className="mt-3 text-base">{protocol.closing}</p>
        </Card>
      </div>
    </div>
  );
}
