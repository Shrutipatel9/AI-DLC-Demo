// The recommendations in exactly three tiers, each with its caption, then the static "consult a
// qualified professional" copy exactly as the server sends it (US8.2).
import {
  CircleCheck,
  Home,
  type LucideIcon,
  ShoppingBag,
  Sparkles,
  Stethoscope,
} from "lucide-react";

import { IconTile } from "@/components/ui/page-header";
import type { ReportRecommendations } from "@/lib/report";

import { NO_RECOMMENDATIONS } from "./messages";

type Item = ReportRecommendations["atHome"][number];

function Tier({
  id,
  heading,
  caption,
  items,
}: {
  id: string;
  heading: string;
  caption: string | undefined;
  items: Item[];
}) {
  return (
    <section
      aria-labelledby={`tier-${id}`}
      className="rounded-card border border-card-border bg-white p-5 shadow-card"
      data-testid={`tier-${id}`}
    >
      <div className="flex items-center gap-3">
        <IconTile
          icon={TIER_ICON.get(id) ?? Sparkles}
          tone={id === "in_clinic" ? "violet" : id === "at_home" ? "teal" : "indigo"}
        />
        <div>
          <h3 id={`tier-${id}`} className="text-lg font-bold text-heading">
            {heading}
          </h3>
          <p className="text-sm text-subheading">{caption}</p>
        </div>
      </div>
      {items.length === 0 ? (
        <p className="mt-2 text-base text-muted">{NO_RECOMMENDATIONS}</p>
      ) : (
        <ul className="mt-4 space-y-2.5 text-base">
          {items.map((item) => (
            <li key={`${item.feature}-${item.text}`} className="flex items-start gap-2.5">
              <CircleCheck
                className="mt-0.5 size-5 shrink-0 text-accent-strong"
                aria-hidden="true"
              />
              <span>
                <span className="font-semibold text-heading">{item.featureTitle}:</span> {item.text}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const TIER_ICON = new Map<string, LucideIcon>([
  ["at_home", Home],
  ["over_the_counter", ShoppingBag],
  ["in_clinic", Stethoscope],
]);

export function Recommendations({ data }: { data: ReportRecommendations }) {
  const captions = new Map(Object.entries(data.tierCaptions));
  return (
    <div className="grid gap-4" data-testid="recommendations">
      <Tier id="at_home" heading="At home" caption={captions.get("at_home")} items={data.atHome} />
      <Tier
        id="over_the_counter"
        heading="Over the counter"
        caption={captions.get("over_the_counter")}
        items={data.overTheCounter}
      />
      <Tier
        id="in_clinic"
        heading="In clinic"
        caption={captions.get("in_clinic")}
        items={data.inClinic}
      />
      <p
        className="rounded-ui border border-[#fedf89] bg-[var(--warning-surface)] p-4 text-base font-medium text-heading"
        data-testid="professional-advice"
      >
        {data.professionalAdviceText}
      </p>
    </div>
  );
}
