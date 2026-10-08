// The recommendations in exactly three tiers, each with its caption, then the static "consult a
// qualified professional" copy exactly as the server sends it (US8.2).
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
    <section aria-labelledby={`tier-${id}`} data-testid={`tier-${id}`}>
      <h3 id={`tier-${id}`} className="text-lg font-semibold text-heading">
        {heading}
      </h3>
      <p className="text-sm italic text-muted">{caption}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-base text-muted">{NO_RECOMMENDATIONS}</p>
      ) : (
        <ul className="mt-2 list-disc space-y-1 pl-6 text-base">
          {items.map((item) => (
            <li key={`${item.feature}-${item.text}`}>
              <span className="font-medium">{item.featureTitle}:</span> {item.text}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Recommendations({ data }: { data: ReportRecommendations }) {
  const captions = new Map(Object.entries(data.tierCaptions));
  return (
    <div className="space-y-6" data-testid="recommendations">
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
      <p className="text-base font-medium text-heading" data-testid="professional-advice">
        {data.professionalAdviceText}
      </p>
    </div>
  );
}
