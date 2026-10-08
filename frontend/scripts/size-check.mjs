// Bundle-size gate for the auth, onboarding, photo, payment and analysis routes (NFR9.5): at most 200 KB of gzipped JavaScript.
//
// For each route it sums the gzipped size of the root main files (build-manifest.json)
// plus every chunk listed in the route's client-reference manifest. Run after `pnpm build`.
import { gzipSync } from "node:zlib";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";

const LIMIT_BYTES = 200 * 1024;
const ROUTES = [
  "/signup",
  "/login",
  "/verify",
  "/home",
  "/forgot-password",
  "/forgot-password/verify",
  "/reset-password",
  "/settings/password",
  "/onboarding",
  "/photos",
  "/payment",
  "/payment/success",
  "/payment/cancel",
  "/analysis",
];
const NEXT_DIR = path.resolve(".next");

function fail(message) {
  console.error(`size-check: ${message}`);
  process.exit(1);
}

if (!existsSync(path.join(NEXT_DIR, "build-manifest.json"))) {
  fail("no build found; run `pnpm build` first");
}

const buildManifest = JSON.parse(readFileSync(path.join(NEXT_DIR, "build-manifest.json"), "utf8"));
const rootFiles = (buildManifest.rootMainFiles ?? []).map((file) => `/_next/${file}`);

function routeChunks(route) {
  const manifestPath = path.join(
    NEXT_DIR,
    "server",
    "app",
    route,
    "page_client-reference-manifest.js",
  );
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- paths are built from the fixed .next build directory, not user input
  if (!existsSync(manifestPath)) fail(`missing client manifest for ${route}`);
  const sandbox = { globalThis: {} };
  sandbox.globalThis = sandbox;
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- paths are built from the fixed .next build directory, not user input
  vm.runInNewContext(readFileSync(manifestPath, "utf8"), sandbox);
  const manifest = sandbox.__RSC_MANIFEST?.[`${route}/page`];
  if (!manifest) fail(`unexpected client manifest shape for ${route}`);
  const chunks = new Set();
  for (const entry of Object.values(manifest.clientModules ?? {})) {
    for (const chunk of entry.chunks ?? []) if (chunk.endsWith(".js")) chunks.add(chunk);
  }
  for (const files of Object.values(manifest.entryJSFiles ?? {})) {
    for (const file of files) chunks.add(file.startsWith("/") ? file : `/_next/${file}`);
  }
  return chunks;
}

function gzippedSize(publicPath) {
  const relative = publicPath.replace(/^\/_next\//, "");
  const file = path.join(NEXT_DIR, relative);
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- paths are built from the fixed .next build directory, not user input
  if (!existsSync(file)) fail(`chunk not found: ${publicPath}`);
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- paths are built from the fixed .next build directory, not user input
  return gzipSync(readFileSync(file), { level: 9 }).length;
}

let failed = false;
for (const route of ROUTES) {
  const files = new Set([...rootFiles, ...routeChunks(route)]);
  const total = [...files].reduce((sum, file) => sum + gzippedSize(file), 0);
  const kb = (total / 1024).toFixed(1);
  const ok = total <= LIMIT_BYTES;
  failed ||= !ok;
  console.log(
    `${ok ? "ok  " : "FAIL"} ${route}: ${kb} KB gzipped JS (${files.size} files, limit 200 KB)`,
  );
}
if (failed) fail("a route exceeds the 200 KB budget");
