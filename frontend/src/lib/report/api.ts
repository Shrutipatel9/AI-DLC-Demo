// Report and Home endpoints (U8; US8.1, US8.5, US11.1). UI code never imports the API client
// (FE-004); it calls these functions through `@/lib/report`.
import { apiBlob, apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

export type Report = components["schemas"]["ReportOut"];
export type ReportFeature = components["schemas"]["FeatureOut"];
export type ReportImage = components["schemas"]["ImageOut"];
export type ReportMetric = components["schemas"]["MetricOut"];
export type ReportAssessments = components["schemas"]["AssessmentsOut"];
export type ReportRecommendations = components["schemas"]["RecommendationsOut"];
export type Home = components["schemas"]["HomeOut"];
export type PriorityFeature = components["schemas"]["PriorityFeatureOut"];
export type RadarAxis = components["schemas"]["RadarAxisOut"];

/** The published report (402 PAYMENT_REQUIRED before payment, 404 REPORT_NOT_READY before it exists). */
export function getReport(): Promise<Report> {
  return apiRequest<Report>("/report");
}

/** The Home Overview data (same errors as the report). */
export function getHome(): Promise<Home> {
  return apiRequest<Home>("/home");
}

/** The report PDF, read with the access token (built on the first request, then cached). */
export function loadReportPdf(): Promise<Blob> {
  return apiBlob("/report/pdf", { timeoutMs: 60_000 });
}
