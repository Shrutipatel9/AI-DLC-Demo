// Price formatting and the checkout redirect (US6.1, US6.2).

/**
 * The configured price for display. `amount` is in minor units (contract C1 Offer); the
 * currency's own number of decimals is used, so 2900 USD is "$29.00" and 2900 JPY is "¥2,900".
 */
export function formatPrice(amount: number, currency: string, locale?: string): string {
  try {
    const format = new Intl.NumberFormat(locale, { style: "currency", currency });
    const digits = format.resolvedOptions().maximumFractionDigits ?? 2;
    return format.format(amount / 10 ** digits);
  } catch {
    // An unknown currency code: show the value without a symbol rather than fail.
    return `${(amount / 100).toFixed(2)} ${currency}`;
  }
}

/** True for an absolute http(s) URL: the only kind of checkout URL the app will follow. */
export function isCheckoutUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

/** Send the browser to the provider's hosted Checkout page (a full navigation). */
export function goToCheckout(url: string): void {
  if (!isCheckoutUrl(url)) throw new Error("The checkout URL is not valid.");
  window.location.assign(url);
}
