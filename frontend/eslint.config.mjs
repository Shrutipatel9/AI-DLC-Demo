// ESLint flat config (team Code Style, BR8.8, BR8.9, AC1.3.4, AC1.4.2).
//
// Layering (client Section 5.3, FE-004, FE-007):
//   UI (src/app, src/components) -> Zustand auth store (src/lib/auth) -> API client
//   (src/lib/api) -> backend.
// UI code may use only the public hooks in `@/lib/auth` (useAuth, useAuthActions).
// It may not import the store, the auth API functions, or the API client, and it may
// not call `fetch` directly. Only src/lib/auth/* may import the store setters.
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import security from "eslint-plugin-security";

const noPersist = {
  name: "zustand/middleware",
  importNames: ["persist"],
  message: "No persisted auth state (FE-002).",
};

const uiRestrictedImports = {
  paths: [noPersist],
  patterns: [
    {
      regex: "^@/lib/auth/(?!hooks$).+",
      message:
        "UI code reads auth state only through useAuth()/useAuthActions() from '@/lib/auth' (FE-007, Section 5.3).",
    },
    {
      regex: "^@/lib/api(/(?!errors$).*)?$",
      message:
        "UI code never calls the API client directly; go through a lib module such as '@/lib/auth' (FE-004).",
    },
    {
      group: ["**/lib/auth/store", "**/lib/auth/api", "**/lib/auth/actions", "**/lib/api/client"],
      message:
        "Relative imports of auth or API internals are not allowed in UI code (Section 5.3).",
    },
  ],
};

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  security.configs.recommended,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["src/app/**/*.{ts,tsx}", "src/components/**/*.{ts,tsx}"],
    ignores: ["**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-imports": ["error", uiRestrictedImports],
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "All HTTP calls go through the API client (FE-004)." },
        { name: "localStorage", message: "No auth state in Web Storage (FE-002)." },
        { name: "sessionStorage", message: "No auth state in Web Storage (FE-002)." },
      ],
      "no-restricted-properties": [
        "error",
        { object: "window", property: "fetch", message: "Use the API client (FE-004)." },
        { object: "window", property: "localStorage", message: "No Web Storage (FE-002)." },
        { object: "window", property: "sessionStorage", message: "No Web Storage (FE-002)." },
      ],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/lib/auth/**", "**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "ImportDeclaration[source.value=/lib\\/auth\\/store$/]",
          message: "Only src/lib/auth/* may import the auth store and its setters.",
        },
      ],
    },
  },
  {
    files: ["src/lib/**/*.{ts,tsx}"],
    ignores: ["src/lib/api/**", "**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Only the API client calls fetch (FE-004)." },
      ],
    },
  },
  {
    files: ["**/*.{ts,tsx,mjs,js}"],
    rules: {
      "no-restricted-imports": ["error", { paths: [noPersist] }],
    },
    ignores: ["src/app/**", "src/components/**"],
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "coverage/**",
    "playwright-report/**",
    "test-results/**",
    "next-env.d.ts",
    "src/lib/api/types.gen.ts",
  ]),
]);

export default eslintConfig;
