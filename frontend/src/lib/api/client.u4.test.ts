// U4 additions to the single API client: multipart uploads and binary (Blob) responses, going
// through the same headers, credentials and 401 -> refresh -> retry path (FE-004, FE-005).
import { beforeEach, describe, expect, it, vi } from "vitest";

import { errorResponse, jsonResponse, mockFetch } from "@/test-utils/fetch-mock";

import {
  apiBlob,
  apiRequest,
  configureApiOrigin,
  setTokenProvider,
  setUnauthorizedHandler,
} from "./client";
import { ApiError } from "./errors";

beforeEach(() => {
  configureApiOrigin("http://api.test");
  setTokenProvider(() => "token-1");
  setUnauthorizedHandler(null);
});

describe("multipart bodies", () => {
  it("sends FormData as it is, without a JSON content type", async () => {
    const requests = mockFetch(() => jsonResponse(200, { ok: true }));
    const form = new FormData();
    form.append("file", new Blob(["x"]), "a.png");
    await apiRequest("/photos/front", { method: "PUT", body: form });
    const [request] = requests;
    expect(request.rawBody).toBe(form);
    expect(request.headers["content-type"]).toBeUndefined();
    expect(request.headers.authorization).toBe("Bearer token-1");
    expect(request.headers["x-requested-with"]).toBe("XMLHttpRequest");
    expect(request.credentials).toBe("include");
  });

  it("still JSON-encodes ordinary bodies", async () => {
    const requests = mockFetch(() => jsonResponse(200, {}));
    await apiRequest("/x", { method: "PUT", body: { a: 1 } });
    expect(requests[0].headers["content-type"]).toBe("application/json");
    expect(requests[0].body).toEqual({ a: 1 });
  });

  it("retries an upload once with the same form after a refresh", async () => {
    let calls = 0;
    const refresh = vi.fn(async () => {
      setTokenProvider(() => "token-2");
    });
    setUnauthorizedHandler(refresh);
    const requests = mockFetch(() =>
      ++calls === 1 ? errorResponse(401, "NOT_AUTHENTICATED") : jsonResponse(200, { ok: true }),
    );
    const form = new FormData();
    await apiRequest("/photos/front", { method: "PUT", body: form });
    expect(refresh).toHaveBeenCalledOnce();
    expect(requests).toHaveLength(2);
    expect(requests[1].rawBody).toBe(form);
    expect(requests[1].headers.authorization).toBe("Bearer token-2");
  });

  it("exposes the photo rejection reasons for an angle", async () => {
    mockFetch(() =>
      errorResponse(422, "PHOTO_REJECTED", {
        details: [
          { angle: "front", reason: "NO_FACE" },
          { angle: "front", reason: "TOO_DARK" },
          { angle: "left_3q", reason: "POSE_MISMATCH" },
        ],
      }),
    );
    const error = await apiRequest("/photos/front", { method: "PUT", body: new FormData() }).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("PHOTO_REJECTED");
    expect((error as ApiError).reasonsFor("front")).toEqual(["NO_FACE", "TOO_DARK"]);
    expect((error as ApiError).reasonsFor("right_3q")).toEqual([]);
  });
});

describe("binary responses", () => {
  it("returns the body as a Blob and accepts any type", async () => {
    const requests = mockFetch(
      () => new Response("image-bytes", { status: 200, headers: { "Content-Type": "image/png" } }),
    );
    const blob = await apiBlob("/media/abc");
    expect(await blob.text()).toBe("image-bytes");
    expect(requests[0].headers.accept).toBe("*/*");
    expect(requests[0].headers.authorization).toBe("Bearer token-1");
  });

  it("turns a 404 into an ApiError like any request", async () => {
    mockFetch(() => errorResponse(404, "NOT_FOUND"));
    await expect(apiBlob("/media/other-users-file")).rejects.toMatchObject({
      status: 404,
      code: "NOT_FOUND",
    });
  });
});
