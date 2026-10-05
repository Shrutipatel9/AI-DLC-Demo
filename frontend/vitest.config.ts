// Vitest configuration (team Testing Posture: Vitest + React Testing Library, 80% lines).
// The coverage floor is a merge gate (NFR8.1) and must not be lowered.
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
    restoreMocks: true,
    unstubGlobals: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/lib/api/types.gen.ts", "e2e/**", "src/**/*.d.ts"],
      reporter: ["text", "text-summary", "lcov"],
      thresholds: {
        lines: 80,
      },
    },
  },
});
