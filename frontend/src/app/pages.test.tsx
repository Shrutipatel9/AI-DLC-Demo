// Page shells, runtime API config and the toast region (US1.9, NFR2.13, BR-009).
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppToaster } from "@/components/ui/toaster";
import { getApiOrigin } from "@/lib/api/client";
import { resetAuthStore } from "@/lib/auth/store";
import { ApiConfigProvider, useApiOrigin } from "@/lib/config/api-config";
import { resetNextMocks } from "@/test-utils/next-mocks";

import LogInPage from "./login/page";
import NotFound from "./not-found";
import RootPage from "./page";
import SignUpPage from "./signup/page";
import VerifyPage from "./verify/page";

const redirect = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return {
    useRouter: () => mocks.router,
    useSearchParams: () => mocks.searchParams.value,
    redirect,
  };
});

describe("pages", () => {
  beforeEach(() => {
    resetAuthStore();
    resetNextMocks();
  });

  it("renders the auth pages inside the public shell", () => {
    const { unmount } = render(<SignUpPage />);
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    unmount();
    render(<LogInPage />);
    expect(screen.getByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });

  it("renders the code page and the not-found page", () => {
    const { unmount } = render(<VerifyPage />);
    expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    unmount();
    render(<NotFound />);
    expect(screen.getByTestId("not-found-next-step-link")).toHaveAttribute("href", "/login");
  });

  it("sends the root to log in", () => {
    RootPage();
    expect(redirect).toHaveBeenCalledWith("/login");
  });

  it("passes the runtime API origin to the client and context", () => {
    function Probe() {
      return <span data-testid="origin">{useApiOrigin()}</span>;
    }
    render(
      <ApiConfigProvider apiOrigin="https://api.runtime.test/">
        <Probe />
      </ApiConfigProvider>,
    );
    expect(screen.getByTestId("origin")).toHaveTextContent("https://api.runtime.test/");
    expect(getApiOrigin()).toBe("https://api.runtime.test");
  });

  it("mounts one toast region", () => {
    render(<AppToaster />);
    expect(document.querySelector("section[aria-label]")).not.toBeNull();
  });
});
