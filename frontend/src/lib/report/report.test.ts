// The report lib: the endpoints, the PDF download and the file save (US8.1, US8.5, US11.1).
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { mockFetch } from "@/test-utils/fetch-mock";
import { newReportState, reportServer } from "@/test-utils/report-server";

import { getHome, getReport, loadReportPdf } from "./api";
import { PDF_FILE_NAME, saveBlob } from "./download";
import { downloadReportPdf } from "./hooks";

beforeEach(() => {
  configureApiOrigin("http://api.test");
});

describe("report API", () => {
  it("reads the report, Home and the PDF from their routes", async () => {
    const requests = mockFetch(reportServer(newReportState()));

    expect((await getReport()).features).toHaveLength(11);
    expect((await getHome()).reportStatus).toBe("ready");
    expect((await loadReportPdf()).type).toBe("application/pdf");

    expect(requests.map((request) => new URL(request.url).pathname)).toEqual([
      "/report",
      "/home",
      "/report/pdf",
    ]);
  });

  it("downloadReportPdf saves a file and reports false when the PDF fails", async () => {
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:pdf");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const state = newReportState();
    mockFetch(reportServer(state));

    expect(await downloadReportPdf()).toBe(true);
    expect(click).toHaveBeenCalledTimes(1);

    state.failPdf = true;
    expect(await downloadReportPdf()).toBe(false);
    expect(click).toHaveBeenCalledTimes(1);
  });
});

describe("saveBlob", () => {
  it("clicks a temporary download link with the file name and cleans up", () => {
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:x");
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    let download = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      download = this.download;
    });

    saveBlob(new Blob(["x"]), PDF_FILE_NAME);

    expect(download).toBe("facial-analysis-report.pdf");
    expect(document.querySelector("a[download]")).toBeNull();
    return new Promise<void>((resolve) =>
      setTimeout(() => {
        expect(revoke).toHaveBeenCalledWith("blob:x");
        resolve();
      }, 5),
    );
  });
});
