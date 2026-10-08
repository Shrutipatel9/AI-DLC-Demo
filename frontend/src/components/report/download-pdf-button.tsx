"use client";

// "Download PDF" (US8.5, US11.1): the PDF is read with the access token and saved as a file.
// A toast says whether it worked (BR-009).
import { Download } from "lucide-react";
import { useState } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { downloadReportPdf } from "@/lib/report";

import { PDF_BUSY, PDF_FAILURE, PDF_SUCCESS } from "./messages";

export function DownloadPdfButton({ testId = "report-download-pdf" }: { testId?: string }) {
  const [busy, setBusy] = useState(false);

  async function onClick() {
    setBusy(true);
    const ok = await downloadReportPdf();
    setBusy(false);
    if (ok) toast.success(PDF_SUCCESS);
    else toast.error(PDF_FAILURE);
  }

  return (
    <Button
      type="button"
      variant="secondary"
      onClick={() => void onClick()}
      disabled={busy}
      aria-busy={busy}
      data-testid={testId}
    >
      <Download className="h-4 w-4" aria-hidden="true" />
      {busy ? PDF_BUSY : "Download PDF"}
    </Button>
  );
}
