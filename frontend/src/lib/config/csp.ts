// Content-Security-Policy builder (NFR2.13, security design section 5).
//
// Production: scripts only from 'self' plus the per-request nonce ('strict-dynamic');
// inline styles are allowed because Tailwind/shadcn/Sonner set style attributes; no
// inline scripts. Development adds 'unsafe-eval' and ws: for hot reload. The API origin
// is read at request time so one build serves every environment.

export interface CspOptions {
  nonce: string;
  apiOrigin: string;
  isDev: boolean;
}

/** A 16-byte random nonce, base64-encoded. */
export function createNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/** Normalise an origin for `connect-src` (no trailing slash, no path). */
export function originOf(value: string | undefined): string {
  if (!value) return "";
  try {
    return new URL(value).origin;
  } catch {
    return "";
  }
}

export function buildCsp({ nonce, apiOrigin, isDev }: CspOptions): string {
  const scriptSrc = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"];
  const connectSrc = ["'self'"];
  if (apiOrigin) connectSrc.push(apiOrigin);
  if (isDev) {
    scriptSrc.push("'unsafe-eval'");
    connectSrc.push("ws:");
  }
  const directives = [
    "default-src 'self'",
    `script-src ${scriptSrc.join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    // blob: shows private photos read through the API client and camera previews (U4).
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src ${connectSrc.join(" ")}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ];
  return directives.join("; ");
}
