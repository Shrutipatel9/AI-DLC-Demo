"use client";

// Runtime API origin (NFR2.13, NFR11.4). The root layout reads the server env `API_ORIGIN`
// at request time and passes it here, so one build serves every environment (no
// build-time NEXT_PUBLIC_* value). The provider hands it to the single API client.
import { createContext, useContext, type ReactNode } from "react";

import { configureApiOrigin } from "@/lib/api/client";

const ApiOriginContext = createContext<string>("");

export function ApiConfigProvider({
  apiOrigin,
  children,
}: {
  apiOrigin: string;
  children: ReactNode;
}) {
  configureApiOrigin(apiOrigin);
  return <ApiOriginContext.Provider value={apiOrigin}>{children}</ApiOriginContext.Provider>;
}

/** The configured API origin (for display or diagnostics only). */
export function useApiOrigin(): string {
  return useContext(ApiOriginContext);
}
