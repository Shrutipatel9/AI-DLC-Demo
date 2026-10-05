// Shared mocks for Next.js navigation and Sonner toasts in component tests.
import { vi } from "vitest";

export const router = {
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
  forward: vi.fn(),
  prefetch: vi.fn(),
};

export const searchParams = { value: new URLSearchParams() };

export const toastMock = { success: vi.fn(), error: vi.fn() };

export function resetNextMocks(): void {
  for (const fn of Object.values(router)) fn.mockReset();
  toastMock.success.mockReset();
  toastMock.error.mockReset();
  searchParams.value = new URLSearchParams();
}
