// Display helpers for the Settings screens.

/** A date for people, such as "1 October 2026", in the browser's locale (UTC day). */
export function formatDate(iso: string, locale?: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "UTC" }).format(date);
}

export function statusText(status: string): string {
  switch (status) {
    case "succeeded":
      return "Paid";
    case "pending":
      return "Pending";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}
