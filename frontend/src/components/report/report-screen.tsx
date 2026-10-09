"use client";

// The report (US8.3-US8.8): one scrolling page. The "Understanding Your Results" preamble comes
// before the first score or feature (AC8.7.2), then the contents list (each entry moves to its
// section and puts focus on that heading, AC8.3.1), the Facial Assessments, the 11 features in
// the report's order, the three recommendation tiers and the limitations. "Download PDF" is
// always one click away (US8.5).
import { ChevronRight, FileText, ListOrdered } from "lucide-react";
import Link from "next/link";
import type { MouseEvent, ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useReport, type Report } from "@/lib/report";

import { ASSESSMENT_SECTIONS, Assessments } from "./assessments";
import { DownloadPdfButton } from "./download-pdf-button";
import { FeatureSection } from "./feature-section";
import {
  ASSESSMENTS_HEADING,
  LIMITATIONS_HEADING,
  LOAD_ERROR,
  NO_REPORT_TEXT,
  NO_REPORT_TITLE,
  RECOMMENDATIONS_HEADING,
  REPORT_TITLE,
  TOC_HEADING,
} from "./messages";
import { Recommendations } from "./recommendations";

/** Move to a section and put focus on its heading (works for mouse, touch and keyboard). */
function goToSection(event: MouseEvent<HTMLAnchorElement>, id: string) {
  event.preventDefault();
  const heading = document.getElementById(`section-${id}`);
  if (!heading) return;
  heading.scrollIntoView?.({ block: "start" });
  heading.focus({ preventScroll: true });
}

function Toc({ report }: { report: Report }) {
  const entries = [
    ...ASSESSMENT_SECTIONS.filter((entry) => hasAssessment(report, entry.id)),
    ...report.features.map((feature) => ({ id: feature.key, title: feature.title })),
    { id: "recommendations", title: RECOMMENDATIONS_HEADING },
  ];
  return (
    <nav
      aria-labelledby="report-toc-heading"
      className="rounded-card border border-card-border bg-white p-5"
      data-testid="report-toc"
    >
      <h2
        id="report-toc-heading"
        className="flex items-center gap-2 text-xl font-bold text-heading"
      >
        <ListOrdered className="size-5 text-accent-strong" aria-hidden="true" />
        {TOC_HEADING}
      </h2>
      <ol className="mt-3 grid list-none gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map((entry) => (
          <li key={entry.id}>
            <a
              href={`#section-${entry.id}`}
              onClick={(event) => goToSection(event, entry.id)}
              className="flex min-h-11 items-center gap-2 rounded-ui px-3 text-[15px] font-medium text-heading transition-colors hover:bg-accent-soft hover:text-accent-deep"
              data-testid={`toc-${entry.id}`}
            >
              <ChevronRight className="size-4 shrink-0 text-accent-strong" aria-hidden="true" />
              {entry.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function hasAssessment(report: Report, id: string): boolean {
  const { symmetry, facialThirds, dimorphism, prototypicality, faceShape } = report.assessments;
  switch (id) {
    case "symmetry":
      return symmetry !== null;
    case "facial-thirds":
      return facialThirds !== null;
    case "dimorphism":
      return dimorphism !== null;
    case "prototypicality":
      return prototypicality !== null;
    default:
      return faceShape !== null;
  }
}

function Heading2({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <h2
      id={id ? `section-${id}` : undefined}
      tabIndex={id ? -1 : undefined}
      className="border-l-4 border-accent-strong pl-3 text-2xl font-bold text-heading"
    >
      {children}
    </h2>
  );
}

export function ReportContent({ report }: { report: Report }) {
  const sections = report.templateSections;
  const understanding = sections.understandingYourResults;
  return (
    <div className="space-y-10" data-testid="report">
      <header className="relative overflow-hidden rounded-[28px] border border-white bg-brand-gradient-soft px-5 py-8 shadow-card sm:px-10 sm:py-12">
        <div className="bg-dot-grid absolute inset-0 opacity-60" aria-hidden="true" />
        <div className="relative space-y-4">
          <p className="inline-flex items-center gap-2 rounded-full border border-accent-soft-border bg-white/80 px-3 py-1 text-sm font-semibold text-accent-deep">
            <FileText className="size-4" aria-hidden="true" />
            FaceIQ report
          </p>
          <h1 className="text-3xl font-extrabold text-heading sm:text-4xl">{REPORT_TITLE}</h1>
          <p className="max-w-2xl text-base text-heading" data-testid="report-introduction">
            {sections.introduction}
          </p>
          <DownloadPdfButton />
        </div>
      </header>

      <section
        aria-labelledby="report-preamble-heading"
        className="rounded-card border border-card-border bg-white p-5 shadow-card sm:p-6"
        data-testid="report-preamble"
      >
        <h2
          id="report-preamble-heading"
          className="border-l-4 border-accent-strong pl-3 text-2xl font-bold text-heading"
        >
          Understanding Your Results
        </h2>
        <p className="mt-2 text-base text-subheading">{understanding.intro}</p>
        <ol className="mt-5 grid gap-3 sm:grid-cols-2">
          {understanding.principles.map((principle, index) => (
            <li
              key={principle.title}
              className="flex gap-4 rounded-ui border border-card-border bg-surface-muted/50 p-4"
            >
              <span
                className="font-display text-2xl font-extrabold text-brand-gradient"
                aria-hidden="true"
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="text-base font-semibold text-heading">{principle.title}</p>
                <p className="text-base">{principle.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <Toc report={report} />

      <section aria-labelledby="report-assessments-heading" className="space-y-6">
        <h2
          id="report-assessments-heading"
          className="border-l-4 border-accent-strong pl-3 text-2xl font-bold text-heading"
        >
          {ASSESSMENTS_HEADING}
        </h2>
        <Assessments assessments={report.assessments} />
      </section>

      <div className="space-y-12">
        {report.features.map((feature) => (
          <FeatureSection key={feature.key} feature={feature} />
        ))}
      </div>

      <section aria-labelledby="section-recommendations" className="space-y-4">
        <Heading2 id="recommendations">{RECOMMENDATIONS_HEADING}</Heading2>
        <Recommendations data={report.recommendations} />
      </section>

      <section
        aria-labelledby="report-limitations-heading"
        className="space-y-3 rounded-card bg-surface-muted p-5 sm:p-6"
      >
        <h2
          id="report-limitations-heading"
          className="border-l-4 border-accent-strong pl-3 text-2xl font-bold text-heading"
        >
          {LIMITATIONS_HEADING}
        </h2>
        <p className="text-base" data-testid="report-limitations">
          {sections.limitations}
        </p>
        <DownloadPdfButton testId="report-download-pdf-bottom" />
      </section>
    </div>
  );
}

export function ReportScreen() {
  const { phase, data, reload } = useReport();

  let body: ReactNode;
  if (phase === "loading") {
    body = (
      <p role="status" className="text-base text-muted" data-testid="report-loading">
        Loading your report…
      </p>
    );
  } else if (phase === "error") {
    body = (
      <div className="space-y-4" data-testid="report-error">
        <p role="alert" className="text-base text-heading">
          {LOAD_ERROR}
        </p>
        <Button onClick={reload} data-testid="report-retry-button">
          Try again
        </Button>
      </div>
    );
  } else if (phase === "none" || data === null) {
    body = (
      <section className="space-y-4" data-testid="report-none">
        <h1 className="text-2xl font-bold text-heading">{NO_REPORT_TITLE}</h1>
        <p className="text-base text-muted">{NO_REPORT_TEXT}</p>
        <Link href="/analysis" className={buttonVariants()} data-testid="report-analysis-link">
          Go to your analysis
        </Link>
      </section>
    );
  } else {
    body = <ReportContent report={data} />;
  }

  return (
    <div className="mx-auto max-w-[900px]">
      {phase === "ready" && data !== null ? body : <Card className="p-4 sm:p-8">{body}</Card>}
    </div>
  );
}
