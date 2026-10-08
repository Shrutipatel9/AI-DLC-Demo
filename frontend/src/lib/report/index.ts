// The only report entry point for UI code (FE-004: UI never imports the API client).
export {
  getHome,
  getReport,
  type Home,
  type PriorityFeature,
  type RadarAxis,
  type Report,
  type ReportAssessments,
  type ReportFeature,
  type ReportImage,
  type ReportMetric,
  type ReportRecommendations,
} from "./api";
export { downloadReportPdf, useHome, useReport, type LoadPhase, type Loaded } from "./hooks";
