// Per-request CSP with a nonce (NFR2.13). Next.js 16 renamed `middleware.ts` to `proxy.ts`
// (the plan's `src/middleware.ts`; same behaviour). The nonce and the policy are set on the
// FORWARDED request headers, so Next.js stamps the nonce on its own scripts, and the
// policy is also set on the response.
import { NextResponse, type NextRequest } from "next/server";

import { buildCsp, createNonce, originOf } from "@/lib/config/csp";

export function proxy(request: NextRequest): NextResponse {
  const nonce = createNonce();
  const policy = buildCsp({
    nonce,
    apiOrigin: originOf(process.env.API_ORIGIN),
    isDev: process.env.NODE_ENV === "development",
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  matcher: [
    {
      // Every route except static assets, image optimisation and the favicon.
      source:
        "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt)$).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
