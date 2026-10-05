// The only payment entry point for UI code (FE-004: UI never imports the API client).
export {
  getOffer,
  getPaymentStatus,
  startCheckout,
  type Offer,
  type PaymentState,
  type PaymentStatus,
} from "./api";
export { formatPrice, goToCheckout, isCheckoutUrl } from "./format";
export { POLL_INTERVAL_MS, usePaymentConfirmation, type Confirmation } from "./confirmation";
