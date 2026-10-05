// The /photos route: protected like every signed-in page, then the photo flow (US5.1).
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, signOutOnce, useAuthStore, type User } from "@/lib/auth/store";
import { jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";
import { newPhotosState, photosServer } from "@/test-utils/photos-server";

import PhotosPage from "./page";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const USER: User = {
  id: "u-1",
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  role: "user",
  memberSince: "2026-10-01T10:00:00Z",
};

describe("PhotosPage", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("waits for the session and sends a signed-out visitor to log in", () => {
    render(<PhotosPage />);
    expect(screen.getByTestId("session-loader")).toBeInTheDocument();
    act(() => {
      signOutOnce("session_expired", useAuthStore.getState().generation);
    });
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("shows the photo requirements to a signed-in user", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
      photosServer(newPhotosState()),
    );
    render(<PhotosPage />);
    expect(await screen.findByTestId("photo-requirements")).toBeInTheDocument();
  });
});
