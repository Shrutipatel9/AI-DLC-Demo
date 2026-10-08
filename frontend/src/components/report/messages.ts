// Plain-language text for the report screens (US8.3-US8.8). The report's own text (introduction,
// preamble, limitations, recommendations advice) comes from the server's configured template.
export const REPORT_TITLE = "Your report";
export const NOT_AVAILABLE_TEXT = "Not available yet";
export const CREATING_TEXT = "Creating…";
export const NO_REPORT_TITLE = "Your report appears after your analysis";
export const NO_REPORT_TEXT = "Once your analysis has finished, your full report will be here.";
export const LOAD_ERROR = "We couldn't load your report. Please try again.";
export const PDF_SUCCESS = "Your PDF is downloading.";
export const PDF_FAILURE = "We couldn't download your PDF. Please try again.";
export const PDF_BUSY = "Preparing your PDF…";

export const ASSESSMENTS_HEADING = "Facial Assessments";
export const RECOMMENDATIONS_HEADING = "Recommendations";
export const LIMITATIONS_HEADING = "Limitations";
export const TOC_HEADING = "Contents";

export const NO_RECOMMENDATIONS = "Nothing in this group. Continue your current routine.";

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function titleCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
