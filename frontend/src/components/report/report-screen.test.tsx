// The report page (US8.3, US8.4, US8.6, US8.7, US8.8: AC8.3.1-AC8.3.3, AC8.4.1-AC8.4.3,
// AC8.6.1, AC8.7.1-AC8.7.5, AC8.8.1, AC8.8.2) and the Download PDF button (AC8.5.1).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, toastMock } from "@/test-utils/next-mocks";
import { makeReport, newReportState, reportServer } from "@/test-utils/report-server";

import { ReportScreen } from "./report-screen";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const FEATURES = [
  "Hair",
  "Eyebrows",
  "Eyes",
  "Nose",
  "Cheeks",
  "Jaw",
  "Lips",
  "Chin",
  "Skin",
  "Neck",
  "Ears",
];

beforeEach(() => {
  resetNextMocks();
  configureApiOrigin("http://api.test");
});

function show(state = newReportState()) {
  const requests = mockFetch(reportServer(state));
  render(<ReportScreen />);
  return { state, requests };
}

describe("The report page", () => {
  it("shows the preamble before the first score or feature (AC8.7.2, AC8.7.3)", async () => {
    show();
    const report = await screen.findByTestId("report");
    expect(screen.getByTestId("report-introduction")).toHaveTextContent("INTRO TEXT");
    const preamble = screen.getByTestId("report-preamble");
    expect(within(preamble).getByText("Principle two.")).toBeInTheDocument();
    const firstScore = screen.getByTestId("symmetry-summary");
    const firstFeature = screen.getByTestId("feature-hair");
    expect(
      preamble.compareDocumentPosition(firstScore) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      preamble.compareDocumentPosition(firstFeature) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(report).toContainElement(screen.getByTestId("report-limitations"));
    expect(screen.getByTestId("report-limitations")).toHaveTextContent("LIMITATIONS TEXT");
  });

  it("lists exactly the 11 features in the report order (AC8.1.1)", async () => {
    show();
    await screen.findByTestId("report");
    const sections = FEATURES.map((title) => screen.getByTestId(`feature-${title.toLowerCase()}`));
    sections.slice(1).forEach((section, index) => {
      expect(
        sections.at(index)!.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    });
    expect(screen.queryByTestId("feature-smile")).toBeNull();
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings.filter((text) => FEATURES.includes(text ?? ""))).toEqual(FEATURES);
  });

  it("moves focus to the section heading from the contents list (AC8.3.1)", async () => {
    show();
    const toc = await screen.findByTestId("report-toc");
    const links = within(toc).getAllByRole("link");
    expect(links).toHaveLength(5 + 11 + 1);
    await userEvent.click(screen.getByTestId("toc-nose"));
    expect(screen.getByRole("heading", { level: 3, name: "Nose" })).toHaveFocus();
    // Keyboard: Enter on a link does the same.
    screen.getByTestId("toc-symmetry").focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("heading", { level: 3, name: "Symmetry" })).toHaveFocus();
  });

  it("shows symmetry with its label and Regional Balance, and the thirds (AC8.3.2, AC8.3.3)", async () => {
    show();
    await screen.findByTestId("report");
    expect(screen.getByTestId("symmetry-summary")).toHaveTextContent("88 out of 100 · High");
    const balance = screen.getByTestId("regional-balance");
    expect(within(balance).getByText("Eyes")).toBeInTheDocument();
    expect(within(balance).getByText("80")).toBeInTheDocument();
    const thirds = screen.getByTestId("thirds-list");
    expect(thirds).toHaveTextContent("Upper third");
    expect(thirds).toHaveTextContent("32%");
    expect(thirds).toHaveTextContent("34%");
  });

  it("shows display-only dimorphism, prototypicality and face shape with text (AC8.8.1, AC8.8.2)", async () => {
    show();
    await screen.findByTestId("report");
    expect(screen.getByTestId("dimorphism-summary")).toHaveTextContent("Balanced");
    const section = screen.getByTestId("assessment-dimorphism");
    expect(within(section).queryAllByRole("slider")).toHaveLength(0);
    expect(within(section).queryAllByRole("textbox")).toHaveLength(0);
    expect(within(section).getAllByRole("meter")).toHaveLength(2);
    expect(screen.getByTestId("prototypicality-summary")).toHaveTextContent("72 out of 100");
    expect(screen.getByTestId("face-shape-wireframe")).toHaveAccessibleName(
      "Face shape outline: oval",
    );
    expect(screen.getByTestId("face-shape-text")).toHaveTextContent(
      "Oval. Slightly longer than wide.",
    );
  });

  it("labels each AI image and gives it alt text; the photo sits next to it (AC8.7.1, AC8.7.4)", async () => {
    show();
    const after = await screen.findByTestId("feature-after-nose");
    await waitFor(() => expect(after).toHaveAttribute("data-state", "loaded"));
    expect(within(after).getByRole("img")).toHaveAttribute(
      "alt",
      "AI-generated illustration — Nose",
    );
    expect(screen.getByTestId("feature-ai-label-nose")).toHaveTextContent(
      "AI-generated illustration",
    );
    const before = screen.getByTestId("feature-before-nose");
    await waitFor(() => expect(before).toHaveAttribute("data-state", "loaded"));
    expect(within(before).getByRole("img")).toHaveAttribute("alt", "Your photo — Nose");
    const feature = screen.getByTestId("feature-nose");
    expect(feature).toHaveTextContent("Narrative for Nose.");
    expect(feature).toHaveTextContent("An idea for Nose.");
    expect(screen.getByTestId("feature-summary-nose")).toHaveTextContent("Nose Summary");
  });

  it("says Not available yet for an image that is not ready, and still shows the text (AC8.7.5)", async () => {
    show(
      newReportState({
        report: makeReport(
          {},
          {
            eyes: {
              after: {
                status: "not_available",
                imageUrl: null,
                aiLabel: "AI-generated illustration",
                alt: "AI-generated illustration — Eyes",
              },
            },
            ears: {
              after: {
                status: "pending",
                imageUrl: null,
                aiLabel: "AI-generated illustration",
                alt: "AI-generated illustration — Ears",
              },
            },
          },
        ),
      }),
    );
    expect(await screen.findByTestId("feature-after-eyes")).toHaveTextContent("Not available yet");
    expect(screen.getByTestId("feature-after-ears")).toHaveTextContent("Creating…");
    expect(screen.queryByTestId("feature-ai-label-eyes")).toBeNull();
    expect(screen.getByTestId("feature-eyes")).toHaveTextContent("Narrative for Eyes.");
  });

  it("lists measurements with units in a table that scrolls inside its own area (AC8.4.1, AC8.4.3)", async () => {
    show();
    const region = await screen.findByTestId("metrics-nose");
    expect(region).toHaveClass("overflow-x-auto");
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toHaveAccessibleName("Nose measurements");
    const table = within(region).getByRole("table");
    expect(within(table).getByText("Nose width")).toBeInTheDocument();
    expect(within(table).getByText("0.31")).toBeInTheDocument();
    expect(within(table).getByText("ratio")).toBeInTheDocument();
  });

  it("says so instead of showing empty numbers for Hair and Neck (AC8.4.2)", async () => {
    show();
    await screen.findByTestId("report");
    expect(screen.getByTestId("metrics-none-hair")).toHaveTextContent("described from the photo");
    expect(screen.queryByTestId("metrics-hair")).toBeNull();
    expect(screen.getByTestId("metrics-none-neck")).toBeInTheDocument();
  });

  it("shows the Skin content: Skincare Protocol and Further Skin Enhancement (AC8.6.1)", async () => {
    show();
    await screen.findByTestId("report");
    const skin = screen.getByTestId("feature-skin");
    expect(within(skin).getByText("Skincare Protocol")).toBeInTheDocument();
    expect(within(skin).getByText("Further Skin Enhancement")).toBeInTheDocument();
  });

  it("shows three tiers with their captions and the professional-advice copy (AC8.2.1, AC8.2.3)", async () => {
    show();
    await screen.findByTestId("report");
    const atHome = screen.getByTestId("tier-at_home");
    expect(atHome).toHaveTextContent("Drink water.");
    expect(atHome).toHaveTextContent("Gentle, at-home.");
    expect(screen.getByTestId("tier-over_the_counter")).toHaveTextContent("Use a moisturiser.");
    expect(screen.getByTestId("tier-in_clinic")).toHaveTextContent("Nothing in this group");
    expect(screen.getByTestId("professional-advice")).toHaveTextContent(
      "Please consult a qualified professional.",
    );
  });
});

describe("Download PDF (US8.5)", () => {
  it("fetches the PDF with the access token, saves it and says so with a toast (AC8.5.1)", async () => {
    const created = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:pdf");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const { state } = show();

    await userEvent.click(await screen.findByTestId("report-download-pdf"));

    await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith("Your PDF is downloading."));
    expect(state.pdfRequests).toBe(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(created).toHaveBeenCalled();
  });

  it("shows an error toast when the PDF cannot be fetched", async () => {
    show(newReportState({ failPdf: true }));

    await userEvent.click(await screen.findByTestId("report-download-pdf"));

    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(
        "We couldn't download your PDF. Please try again.",
      ),
    );
    expect(toastMock.success).not.toHaveBeenCalled();
  });
});

describe("When there is no report to show", () => {
  it("points to the analysis for a paid user whose report is not ready (404)", async () => {
    show(newReportState({ report: { status: 404, code: "REPORT_NOT_READY" } }));
    expect(await screen.findByTestId("report-none")).toHaveTextContent("after your analysis");
    expect(screen.getByTestId("report-analysis-link")).toHaveAttribute("href", "/analysis");
  });

  it("treats 402 the same way (the payment comes first)", async () => {
    show(newReportState({ report: { status: 402, code: "PAYMENT_REQUIRED" } }));
    expect(await screen.findByTestId("report-none")).toBeInTheDocument();
  });

  it("offers Try again after a load error, then shows the report", async () => {
    const state = newReportState({ report: { status: 500, code: "INTERNAL_ERROR" } });
    show(state);
    expect(await screen.findByTestId("report-error")).toHaveTextContent(
      "couldn't load your report",
    );
    state.report = makeReport();
    await userEvent.click(screen.getByTestId("report-retry-button"));
    expect(await screen.findByTestId("report")).toBeInTheDocument();
  });
});
