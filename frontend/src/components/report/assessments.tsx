// The Facial Assessments (US8.3, US8.8): symmetry with Regional Balance, facial thirds,
// masculine/feminine balance (display only), prototypicality and face shape. Every value is also
// plain text or a table (AC8.3.3, AC8.8.1, AC8.8.2). Nothing here is an input.
import type { ReactNode } from "react";

import type { ReportAssessments } from "@/lib/report";

import { FaceShapeWireframe } from "./face-shape";
import { percent, titleCase } from "./messages";

export const ASSESSMENT_SECTIONS = [
  { id: "symmetry", title: "Symmetry" },
  { id: "facial-thirds", title: "Facial thirds" },
  { id: "dimorphism", title: "Masculine and feminine balance" },
  { id: "prototypicality", title: "Prototypicality" },
  { id: "face-shape", title: "Face shape" },
] as const;

function Heading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h3 id={`section-${id}`} tabIndex={-1} className="text-xl font-semibold text-heading">
      {children}
    </h3>
  );
}

/** A horizontal bar for a 0-100 value; the number is always printed beside it. */
function Bar({ value, label }: { value: number; label: string }) {
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      className="h-3 w-full overflow-hidden rounded-full bg-[#e3e9ee]"
    >
      <div className="h-full bg-accent-strong" style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  );
}

function Section({ id, children }: { id: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={`section-${id}`}
      className="space-y-3"
      data-testid={`assessment-${id}`}
    >
      {children}
    </section>
  );
}

export function Assessments({ assessments }: { assessments: ReportAssessments }) {
  const { symmetry, facialThirds, dimorphism, prototypicality, faceShape } = assessments;
  return (
    <div className="space-y-8">
      {symmetry ? (
        <Section id="symmetry">
          <Heading id="symmetry">Symmetry</Heading>
          <p className="text-base text-heading" data-testid="symmetry-summary">
            <strong>{symmetry.score}</strong> out of 100 · {titleCase(symmetry.label)}
          </p>
          <Bar value={symmetry.score} label="Symmetry score out of 100" />
          <table className="w-full max-w-md text-left text-base" data-testid="regional-balance">
            <caption className="mb-1 text-left text-sm font-medium text-muted">
              Regional Balance
            </caption>
            <thead>
              <tr>
                <th scope="col" className="py-1 pr-4 font-semibold">
                  Region
                </th>
                <th scope="col" className="py-1 font-semibold">
                  Score
                </th>
              </tr>
            </thead>
            <tbody>
              {symmetry.regionalBalance.map((region) => (
                <tr key={region.region} className="border-t border-card-border">
                  <th scope="row" className="py-1 pr-4 font-normal">
                    {titleCase(region.region)}
                  </th>
                  <td className="py-1">{region.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      ) : null}

      {facialThirds ? (
        <Section id="facial-thirds">
          <Heading id="facial-thirds">Facial thirds</Heading>
          <p className="text-sm text-muted">Each third as a share of your face height.</p>
          <ul className="space-y-2" data-testid="thirds-list">
            {(
              [
                ["Upper third", facialThirds.upper],
                ["Middle third", facialThirds.middle],
                ["Lower third", facialThirds.lower],
              ] as const
            ).map(([label, share]) => (
              <li key={label} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3">
                <span className="text-base">{label}</span>
                <Bar value={Math.round(share * 100)} label={`${label} share of face height`} />
                <span className="text-base font-medium">{percent(share)}</span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {dimorphism ? (
        <Section id="dimorphism">
          <Heading id="dimorphism">Masculine and feminine balance</Heading>
          <p className="text-base text-heading" data-testid="dimorphism-summary">
            Overall: {titleCase(dimorphism.label)}
          </p>
          <ul className="space-y-2">
            <li className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3">
              <span>Masculine</span>
              <Bar
                value={Math.round(dimorphism.masculinity)}
                label="Masculine reading out of 100"
              />
              <span className="font-medium">{Math.round(dimorphism.masculinity)}</span>
            </li>
            <li className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3">
              <span>Feminine</span>
              <Bar value={Math.round(dimorphism.femininity)} label="Feminine reading out of 100" />
              <span className="font-medium">{Math.round(dimorphism.femininity)}</span>
            </li>
          </ul>
          <p className="text-sm text-muted">
            These readings are for information only; you cannot change them.
          </p>
        </Section>
      ) : null}

      {prototypicality !== null ? (
        <Section id="prototypicality">
          <Heading id="prototypicality">Prototypicality</Heading>
          <p className="text-base text-heading" data-testid="prototypicality-summary">
            <strong>{Math.round(prototypicality)}</strong> out of 100
          </p>
          <Bar value={Math.round(prototypicality)} label="Prototypicality out of 100" />
        </Section>
      ) : null}

      {faceShape ? (
        <Section id="face-shape">
          <Heading id="face-shape">Face shape</Heading>
          <div className="flex items-center gap-6">
            <FaceShapeWireframe name={faceShape.name} />
            <p className="text-base" data-testid="face-shape-text">
              <strong>{titleCase(faceShape.name)}.</strong> {faceShape.description}
            </p>
          </div>
        </Section>
      ) : null}
    </div>
  );
}
