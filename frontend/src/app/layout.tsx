import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { headers } from "next/headers";
import type { ReactNode } from "react";

import { AuthBootstrap } from "@/components/app/auth-bootstrap";
import { ConfirmDialogHost } from "@/components/feedback/confirm-dialog";
import { AppToaster } from "@/components/ui/toaster";
import { ApiConfigProvider } from "@/lib/config/api-config";

import "./globals.css";

// Inter is self-hosted by next/font at build time (no third-party requests at runtime).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "AI Facial Analysis",
  description: "Your personal facial analysis and report.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // Reading request headers makes every page render per request, which the CSP nonce
  // requires (NFR2.13). API_ORIGIN is a server env var read at request time.
  const requestHeaders = await headers();
  const nonce = requestHeaders.get("x-nonce") ?? undefined;
  const apiOrigin = process.env.API_ORIGIN ?? "";

  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen antialiased" data-nonce-present={nonce ? "true" : "false"}>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-[var(--radius)] focus:bg-white focus:px-4 focus:py-2"
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
