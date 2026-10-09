import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import { headers } from "next/headers";
import type { ReactNode } from "react";

import { AuthBootstrap } from "@/components/app/auth-bootstrap";
import { ConfirmDialogHost } from "@/components/feedback/confirm-dialog";
import { AppToaster } from "@/components/ui/toaster";
import { ApiConfigProvider } from "@/lib/config/api-config";

import "./globals.css";

// Inter (body) and Plus Jakarta Sans (headings) are self-hosted by next/font at build time (no third-party requests at runtime).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-jakarta",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FaceIQ — AI facial analysis",
  description:
    "FaceIQ turns three photos into a personal facial analysis: symmetry, proportions, face shape and AI-generated visuals.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // Reading request headers makes every page render per request, which the CSP nonce
  // requires (NFR2.13). API_ORIGIN is a server env var read at request time.
  const requestHeaders = await headers();
  const nonce = requestHeaders.get("x-nonce") ?? undefined;
  const apiOrigin = process.env.API_ORIGIN ?? "";

  return (
    <html lang="en" className={`${inter.variable} ${jakarta.variable}`}>
      <body className="min-h-screen antialiased" data-nonce-present={nonce ? "true" : "false"}>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-ui focus:bg-white focus:px-4 focus:py-2"
          data-testid="skip-to-content-link"
        >
          Skip to content
        </a>
        <ApiConfigProvider apiOrigin={apiOrigin}>
          <AuthBootstrap />
          {children}
        </ApiConfigProvider>
        <AppToaster />
        <ConfirmDialogHost />
      </body>
    </html>
  );
}
