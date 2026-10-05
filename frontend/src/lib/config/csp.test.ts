// CSP builder and the proxy (NFR2.13). Next.js 16's proxy.ts replaces middleware.ts.
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, proxy } from "@/proxy";

import { buildCsp, createNonce, originOf } from "./csp";

describe("buildCsp", () => {
  it("is strict in production: nonce + strict-dynamic, no inline or eval scripts", () => {
    const policy = buildCsp({ nonce: "abc", apiOrigin: "https://api.example.com", isDev: false });
    expect(policy).toContain("script-src 'self' 'nonce-abc' 'strict-dynamic'");
    expect(policy).not.toContain("unsafe-eval");
    expect(policy).not.toMatch(/script-src[^;]*unsafe-inline/);
    expect(policy).toContain("connect-src 'self' https://api.example.com");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("object-src 'none'");
    // Private photos are shown from blob: URLs read through the API client (U4).
    expect(policy).toContain("img-src 'self' data: blob:");
  });

  it("adds eval and websockets only in development", () => {
    const policy = buildCsp({ nonce: "n", apiOrigin: "", isDev: true });
    expect(policy).toContain("'unsafe-eval'");
    expect(policy).toContain("connect-src 'self' ws:");
  });

  it("creates fresh base64 nonces and normalises origins", () => {
    const first = createNonce();
    expect(first).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    expect(createNonce()).not.toBe(first);
    expect(originOf("http://localhost:8000/path?q=1")).toBe("http://localhost:8000");
    expect(originOf("not a url")).toBe("");
    expect(originOf(undefined)).toBe("");
  });
});

describe("proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("sets the CSP on the response and forwards the nonce on the request", () => {
    vi.stubEnv("API_ORIGIN", "http://localhost:8000");
    vi.stubEnv("NODE_ENV", "production");
    const response = proxy(new NextRequest("http://localhost:3000/login"));
    const policy = response.headers.get("Content-Security-Policy") ?? "";
    expect(policy).toContain("connect-src 'self' http://localhost:8000");
    expect(policy).not.toContain("unsafe-eval");
    const forwardedNonce = response.headers.get("x-middleware-request-x-nonce");
    expect(forwardedNonce).toBeTruthy();
    expect(policy).toContain(`'nonce-${forwardedNonce}'`);
    expect(response.headers.get("x-middleware-request-content-security-policy")).toBe(policy);
  });

  it("reads the API origin at request time and uses the development variant", () => {
    vi.stubEnv("API_ORIGIN", "https://api.other.test");
    vi.stubEnv("NODE_ENV", "development");
    const policy = proxy(new NextRequest("http://localhost:3000/")).headers.get(
      "Content-Security-Policy",
    );
    expect(policy).toContain("https://api.other.test");
    expect(policy).toContain("'unsafe-eval'");
  });

  it("skips static assets and prefetches", () => {
    const [matcher] = config.matcher;
    // eslint-disable-next-line security/detect-non-literal-regexp -- the pattern is our own matcher constant
    const pattern = new RegExp(`^${matcher.source}$`);
    expect(pattern.test("/login")).toBe(true);
    expect(pattern.test("/_next/static/chunks/a.js")).toBe(false);
    expect(pattern.test("/favicon.ico")).toBe(false);
    expect(matcher.missing.map((item) => item.key)).toEqual(["next-router-prefetch", "purpose"]);
  });
});
