"use client";

// Home Overview (US11.1, US11.3): shown once a report exists. Key stats, the before/potential
// pair, "Priority Features to Improve", the Treatment Protocol card (Phase 01), the six-axis
// radar chart with its text alternative, the report status and the PDF download.
import {
  Activity,
  ArrowRight,
  ClipboardCheck,
  Crosshair,
  Gauge,
  type LucideIcon,
  Sparkles,
  Target,
  Timer,
  Wand2,
} from "lucide-react";
import Link from "next/link";

import { PhotoThumbnail } from "@/components/photos/photo-thumbnail";
import { DownloadPdfButton } from "@/components/report/download-pdf-button";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { IconTile } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";
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

function Stat({
  label,
  value,
  testId,
  icon,
  tone,
}: {
  label: string;
  value: string;
  testId: string;
  icon: LucideIcon;
  tone: "indigo" | "teal" | "violet";
}) {
  return (
    <div className="flex items-center gap-4 rounded-card border border-card-border bg-white p-5 shadow-card">
      <IconTile icon={icon} tone={tone} />
      <div>
        <p className="text-sm font-medium text-subheading">{label}</p>
        <p className="mt-0.5 font-display text-2xl font-bold text-heading" data-testid={testId}>
          {value}
        </p>
      </div>
    </div>
  );
}

function CardTitle({ icon: Icon, children }: { icon: LucideIcon; children: string }) {
  return (
    <h2 className="flex items-center gap-2.5 text-xl font-bold text-heading">
      <Icon className="size-5 text-accent-strong" aria-hidden="true" />
      {children}
    </h2>
  );
}

function Chip({ children }: { children: string }) {
  return (
    <span className="absolute left-2 top-2 rounded-md bg-surface-ink px-2 py-1 text-xs font-bold uppercase text-white">
      {children}
    </span>
  );
}

export function HomeOverview({ home, name }: { home: Home; name: string }) {
  const { protocol } = home;
  return (
    <div className="space-y-6" data-testid="home-overview">
      <section className="relative overflow-hidden rounded-[28px] bg-surface-ink px-6 py-8 text-white shadow-raised sm:px-10 sm:py-10">
        <div
          aria-hidden="true"
          className="absolute -right-16 -top-24 size-80 rounded-full bg-[#4f46e5] opacity-50 blur-[90px]"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-28 left-1/3 size-72 rounded-full bg-[#0d9488] opacity-30 blur-[90px]"
        />
        <div className="relative">
          <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-sm font-semibold text-[#c7d2fe]">
            <Sparkles className="size-4" aria-hidden="true" />
            Your FaceIQ dashboard
          </p>
          <h1 className="mt-4 text-3xl font-extrabold sm:text-4xl" data-testid="home-greeting">
            Hi, {name}
          </h1>
          <p className="mt-2 text-lg text-[#cbd5e1]" data-testid="home-status" aria-live="polite">
            Your report is ready.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/report"
              className={cn(buttonVariants(), "bg-white text-accent-deep hover:bg-white/90")}
              data-testid="home-report-link"
            >
              View my report
              <ArrowRight aria-hidden="true" />
            </Link>
            <DownloadPdfButton testId="home-download-pdf" />
            <Link
              href="/visuals"
              className={cn(
                buttonVariants({ variant: "ghost" }),
                "border border-white/20 text-white hover:bg-white/10",
              )}
              data-testid="home-visuals-link"
            >
              <Wand2 aria-hidden="true" />
              AI Visuals
            </Link>
          </div>
        </div>
      </section>

      <section aria-label="Key stats" className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Overall score"
          value={home.overallScore === null ? "Not scored" : `${home.overallScore}/100`}
          testId="home-stat-score"
          icon={Gauge}
          tone="indigo"
        />
        <Stat
          label="Evaluated"
          value={`${home.evaluatedPoints} points`}
          testId="home-stat-points"
          icon={Crosshair}
          tone="teal"
        />
        <Stat
          label="Analysis time"
          value={durationText(home.analysisDurationSeconds)}
          testId="home-stat-time"
          icon={Timer}
          tone="violet"
        />
      </section>

      <Card>
        <CardTitle icon={Wand2}>Before and potential</CardTitle>
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
              <div className="flex aspect-[4/5] w-full items-center justify-center rounded-ui border border-card-border bg-white p-3 text-center text-sm font-medium text-heading">
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
        <CardTitle icon={Target}>Priority Features to Improve</CardTitle>
        {home.priorityFeatures.length === 0 ? (
          <p className="mt-2 text-base text-muted">No feature could be scored from your photos.</p>
        ) : (
          <ul className="mt-4 grid gap-4 md:grid-cols-2" data-testid="home-priorities">
            {home.priorityFeatures.map((feature) => (
              <li
                key={feature.key}
                className="rounded-ui border border-card-border bg-surface-muted/50 p-4"
                data-testid={`home-priority-${feature.key}`}
              >
                <p className="text-base font-semibold text-heading">
                  {feature.title} · {feature.score}/100 · {feature.label}
                </p>
                <div
                  aria-hidden="true"
                  className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white"
                >
                  <div
                    className="h-full rounded-full bg-brand-gradient"
                    style={{ width: `${Math.max(0, Math.min(100, feature.score))}%` }}
                  />
                </div>
                <ul className="mt-3 list-disc space-y-0.5 pl-5 text-[15px] text-foreground">
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
          <div className="mb-2">
            <CardTitle icon={Activity}>Harmony Profile</CardTitle>
          </div>
          <RadarChart axes={home.harmonyProfile} />
        </Card>
        <Card data-testid="home-protocol">
          <CardTitle icon={ClipboardCheck}>Treatment Protocol</CardTitle>
          <p className="mt-3 inline-flex rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-accent-deep">
            {protocol.phaseLabel}
          </p>
          <p className="mt-2 text-lg font-bold text-heading">{protocol.title}</p>
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
