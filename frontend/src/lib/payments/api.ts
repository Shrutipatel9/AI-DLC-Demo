// Payment endpoints (contract C1 /payments; US6.1, US6.2, US6.5). UI code never imports the API
// client (FE-004); it calls these functions through `@/lib/payments`.
import { apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

type Schemas = components["schemas"];

export type Offer = Schemas["OfferOut"];
export type PaymentStatus = Schemas["PaymentStatusOut"];
export type PaymentState = PaymentStatus["state"];

/** The configured price, currency and what payment unlocks (FR7.1, FR7.3). */
export function getOffer(): Promise<Offer> {
  return apiRequest<Offer>("/payments/offer");
}

/** Create a hosted Checkout session; resolves to the URL the browser must go to (US6.2). */
export async function startCheckout(): Promise<string> {
  const { checkoutUrl } = await apiRequest<Schemas["CheckoutOut"]>("/payments/checkout", {
    method: "POST",
  });
  return checkoutUrl;
}

/** none / pending / paid; changes only when the server receives the verified webhook. */
export function getPaymentStatus(): Promise<PaymentStatus> {
  return apiRequest<PaymentStatus>("/payments/status");
}
