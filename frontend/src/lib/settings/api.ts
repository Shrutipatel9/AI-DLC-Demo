// Settings endpoints (US11.4, US11.6). UI code never imports the API client (FE-004); it calls
// these functions through `@/lib/settings`.
import { apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

type Schemas = components["schemas"];

export type AccountInfo = Schemas["AccountOut"];
export type Billing = Schemas["BillingOut"];
export type PaymentRecord = Schemas["PaymentRecordOut"];

/** Name, email, verification status and member-since date (read only). */
export function getAccountInfo(): Promise<AccountInfo> {
  return apiRequest<AccountInfo>("/settings/account");
}

/** The caller's payments, newest first. */
export function getBilling(): Promise<Billing> {
  return apiRequest<Billing>("/settings/billing");
}
