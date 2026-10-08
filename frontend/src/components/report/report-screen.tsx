"use client";

// The report (US8.3-US8.8): one scrolling page. The "Understanding Your Results" preamble comes
// before the first score or feature (AC8.7.2), then the contents list (each entry moves to its
// section and puts focus on that heading, AC8.3.1), the Facial Assessments, the 11 features in
// the report's order, the three recommendation tiers and the limitations. "Download PDF" is
// always one click away (US8.5).
import Link from "next/link";
import type { MouseEvent, ReactNode } from "react";

import { Button } from "@/components/ui/button";
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
    <nav aria-labelledby="report-toc-heading" data-testid="report-toc">
      <h2 id="report-toc-heading" className="text-xl font-semibold text-heading">
        {TOC_HEADING}
      </h2>
      <ol className="mt-2 grid list-none gap-1 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map((entry) => (
          <li key={entry.id}>
            <a
              href={`#section-${entry.id}`}
              onClick={(event) => goToSection(event, entry.id)}
              className="inline-flex min-h-11 items-center text-base text-accent-strong underline"
              data-testid={`toc-${entry.id}`}
            >
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
      className="text-2xl font-bold text-heading"
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
      <header className="space-y-3">
        <h1 className="text-3xl font-bold text-heading">{REPORT_TITLE}</h1>
        <p className="text-base text-heading" data-testid="report-introduction">
          {sections.introduction}
        </p>
        <DownloadPdfButton />
      </header>

      <section aria-labelledby="report-preamble-heading" data-testid="report-preamble">
        <h2 id="report-preamble-heading" className="text-2xl font-bold text-heading">
          Understanding Your Results
        </h2>
        <p className="mt-2 text-base text-muted">{understanding.intro}</p>
        <ol className="mt-4 space-y-3">
          {understanding.principles.map((principle, index) => (
            <li key={principle.title} className="flex gap-4">
              <span className="text-2xl font-bold text-accent-strong" aria-hidden="true">
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
        <h2 id="report-assessments-heading" className="text-2xl font-bold text-heading">
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

      <section aria-labelledby="report-limitations-heading" className="space-y-2">
        <h2 id="report-limitations-heading" className="text-2xl font-bold text-heading">
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
        <Link
          href="/analysis"
          className="inline-flex min-h-11 items-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
          data-testid="report-analysis-link"
        >
          Go to your analysis
        </Link>
      </section>
    );
  } else {
    body = <ReportContent report={data} />;
  }

  return (
    <div className="mx-auto max-w-[900px]">
      <Card className="p-4 sm:p-8">{body}</Card>
    </div>
  );
}
