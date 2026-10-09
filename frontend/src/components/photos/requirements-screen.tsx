"use client";

// The photo requirements, shown before any capture (US5.1; FR-005, [PC] §2): the 7 rules, each
// with its example illustration, then the configured angles in order (AC5.1.2).
import { ArrowRight, Camera } from "lucide-react";

import { Button } from "@/components/ui/button";
import { IconTile } from "@/components/ui/page-header";
import type { PhotoRequirements } from "@/lib/photos";

import { AngleIllustration, RuleIllustration } from "./illustrations";

export function RequirementsScreen({
  requirements,
  onContinue,
}: {
  requirements: PhotoRequirements;
  onContinue: () => void;
}) {
  return (
    <section className="space-y-6" data-testid="photo-requirements">
      <div className="flex items-start gap-4">
        <IconTile icon={Camera} className="hidden sm:inline-flex" />
        <div>
          <h1 className="text-2xl font-bold text-heading sm:text-[28px]">
            Before you take your photos
          </h1>
          <p className="mt-1.5 text-base text-subheading">
            Follow these rules so your photos pass the first time.
          </p>
        </div>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {requirements.rules.map((rule) => (
          <li
            key={rule.id}
            className="flex items-center gap-3 rounded-ui border border-card-border bg-surface-muted/60 p-3"
            data-testid={`photo-rule-${rule.id}`}
          >
            <RuleIllustration ruleId={rule.id} />
            <span className="text-base text-heading">{rule.text}</span>
          </li>
        ))}
      </ul>
      <div>
        <h2 className="text-lg font-semibold text-heading">
          You&apos;ll take {requirements.angles.length} photos
        </h2>
        <ol className="mt-3 flex flex-wrap gap-4" data-testid="photo-angle-list">
          {requirements.angles.map((angle, index) => (
            <li
              key={angle.id}
              className="flex w-28 flex-col items-center gap-2 rounded-ui border border-card-border bg-white p-3 text-center"
            >
              <AngleIllustration direction={angle.illustration} className="h-20 w-16" />
              <span className="text-sm font-semibold text-heading">
                {index + 1}. {angle.label}
              </span>
            </li>
          ))}
        </ol>
      </div>
      <Button onClick={onContinue} data-testid="photo-requirements-continue">
        I&apos;m ready
        <ArrowRight aria-hidden="true" />
      </Button>
    </section>
  );
}
