// A small, scripted stand-in for the /report, /home and /report/pdf API and the private /media
// bytes, used with `mockFetch` in component tests. Test-only module.
import type { components } from "@/lib/api/types.gen";

import { errorResponse, jsonResponse, type RecordedRequest } from "./fetch-mock";

export type Report = components["schemas"]["ReportOut"];
export type Feature = components["schemas"]["FeatureOut"];
export type Home = components["schemas"]["HomeOut"];

const AI_LABEL = "AI-generated illustration";
const KEYS = [
  ["hair", "Hair"],
  ["eyebrows", "Eyebrows"],
  ["eyes", "Eyes"],
  ["nose", "Nose"],
  ["cheeks", "Cheeks"],
  ["jaw", "Jaw"],
  ["lips", "Lips"],
  ["chin", "Chin"],
  ["skin", "Skin"],
  ["neck", "Neck"],
  ["ears", "Ears"],
] as const;

export function makeFeature(key: string, title: string, overrides: Partial<Feature> = {}): Feature {
  const unmeasured = key === "hair" || key === "neck";
  return {
    key,
    title,
    narrative: `Narrative for ${title}.`,
    summary: `Summary for ${title}.`,
    potentialIdeas: [`An idea for ${title}.`],
    metrics: unmeasured
      ? []
      : [{ name: `${key}_width_ratio`, label: `${title} width`, value: 0.31, unit: "ratio" }],
    noMeasurementReason: unmeasured ? `${title} is described from the photo only.` : null,
    beforeImageUrl: "/media/front",
    beforeAlt: `Your photo — ${title}`,
    after: {
      status: "ready",
      imageUrl: `/media/after-${key}`,
      aiLabel: AI_LABEL,
      alt: `${AI_LABEL} — ${title}`,
    },
    subSections:
      key === "skin"
        ? [
            { heading: "Skincare Protocol", body: "Cleanser, moisturiser, sun protection." },
            { heading: "Further Skin Enhancement", body: "Patch-test new actives." },
          ]
        : [],
    ...overrides,
  };
}

export function makeReport(
  overrides: Partial<Report> = {},
  features: Partial<Record<string, Partial<Feature>>> = {},
): Report {
  return {
    reportId: "11111111-1111-4111-8111-111111111111",
    publishedAt: "2026-10-08T10:00:00Z",
    templateVersion: "u8-v1",
    templateSections: {
      introduction: "INTRO TEXT",
      understandingYourResults: {
        intro: "Please read these four points first.",
        principles: [
          { title: "Principle one.", text: "Text one." },
          { title: "Principle two.", text: "Text two." },
          { title: "Principle three.", text: "Text three." },
          { title: "Principle four.", text: "Text four." },
        ],
      },
      limitations: "LIMITATIONS TEXT",
      disclaimerPoints: ["Not a diagnosis."],
      privacyPoints: ["Private to you."],
    },
    assessments: {
      symmetry: {
        score: 88,
        label: "high",
        regionalBalance: [
          { region: "eyes", score: 90 },
          { region: "mouth", score: 80 },
        ],
      },
      facialThirds: { upper: 0.32, middle: 0.34, lower: 0.34 },
      dimorphism: { masculinity: 55, femininity: 45, label: "balanced" },
      prototypicality: 72.4,
      faceShape: { name: "oval", description: "Slightly longer than wide." },
    },
    features: KEYS.map(([key, title]) =>
      makeFeature(key, title, features[key as keyof typeof features]),
    ),
    recommendations: {
      atHome: [{ feature: "skin", featureTitle: "Skin", text: "Drink water." }],
      overTheCounter: [{ feature: "skin", featureTitle: "Skin", text: "Use a moisturiser." }],
      inClinic: [],
      tierCaptions: {
        at_home: "Gentle, at-home.",
        over_the_counter: "Over-the-counter level.",
        in_clinic: "Discuss with a professional.",
      },
      professionalAdviceText: "Please consult a qualified professional.",
    },
    aiLabel: AI_LABEL,
    pdfUrl: "/report/pdf",
    ...overrides,
  };
}

export function makeHome(overrides: Partial<Home> = {}): Home {
  return {
    reportStatus: "ready",
    overallScore: 77,
    evaluatedPoints: 42,
    analysisDurationSeconds: 72,
    priorityFeatures: [
      {
        key: "nose",
        title: "Nose",
        score: 48,
        label: "Needs attention",
        attributes: [{ name: "Nose width", value: "wider or larger than typical" }],
      },
      { key: "jaw", title: "Jaw", score: 66, label: "Balanced", attributes: [] },
      { key: "lips", title: "Lips", score: 71, label: "Balanced", attributes: [] },
    ],
    harmonyProfile: [
      { axis: "Harmony", value: 77 },
      { axis: "Symmetry", value: 88 },
      { axis: "Smoothness", value: null },
      { axis: "Jawline", value: 66 },
      { axis: "Skin", value: 70 },
      { axis: "Volume", value: 71 },
    ],
    protocol: {
      phaseLabel: "PHASE 01",
      title: "Foundation and Everyday Care",
      timing: "Immediate to weeks 1-12",
      actions: ["Skin: Drink water."],
      closing: "This phase comes first.",
    },
    beforeImageUrl: "/media/front",
    potentialImageUrl: "/media/after-hair",
    aiLabel: AI_LABEL,
    publishedAt: "2026-10-08T10:00:00Z",
    pdfUrl: "/report/pdf",
    ...overrides,
  };
}

export interface ReportServerState {
  /** What GET /report answers: the report, or an error status and code. */
  report: Report | { status: number; code: string };
  home: Home | { status: number; code: string };
  /** When true, GET /report/pdf fails with 500. */
  failPdf: boolean;
  pdfRequests: number;
}

export function newReportState(overrides: Partial<ReportServerState> = {}): ReportServerState {
  return { report: makeReport(), home: makeHome(), failPdf: false, pdfRequests: 0, ...overrides };
}

/** A `mockFetch` handler serving GET /report, /home, /report/pdf and /media/*. */
export function reportServer(state: ReportServerState) {
  return (request: RecordedRequest): Response | undefined => {
    const path = new URL(request.url, "http://x").pathname;
    if (request.method !== "GET") return undefined;
    if (path.startsWith("/media/")) {
      return new Response(new Uint8Array([137, 80, 78, 71]), {
        status: 200,
        headers: { "Content-Type": "image/png" },
      });
    }
    if (path === "/report/pdf") {
      state.pdfRequests += 1;
      if (state.failPdf) return errorResponse(500, "INTERNAL_ERROR");
      return new Response(new Uint8Array([37, 80, 68, 70]), {
        status: 200,
        headers: { "Content-Type": "application/pdf" },
      });
    }
    for (const [route, answer] of [
      ["/report", state.report],
      ["/home", state.home],
    ] as const) {
      if (path === route) {
        return "reportId" in answer || "reportStatus" in answer
          ? jsonResponse(200, answer)
          : errorResponse(answer.status, answer.code);
      }
    }
    return undefined;
  };
}
