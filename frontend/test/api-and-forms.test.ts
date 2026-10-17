import { describe, expect, it, vi } from "vitest";

import { ApiError, api, request } from "@/lib/api";
import { verifySchema } from "@/components/verification/verify-form";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("API client", () => {
  it("calls the same-origin proxy, never the backend directly", async () => {
    const fetch = mockFetch(200, { items: [], total: 0, limit: 50, offset: 0 });
    await api.listDocuments({ q: "dropout", status: "completed" });
    expect(fetch.mock.calls[0][0]).toBe("/api/backend/documents?q=dropout&status=completed");
  });

  it("turns the backend error envelope into an ApiError", async () => {
    mockFetch(409, { error: { code: "duplicate_document", message: "This PDF is already in your library.", request_id: "req-1", details: { document_id: "d1" } } });
    const error = await request("/documents/upload", { method: "POST" }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "duplicate_document", requestId: "req-1", message: "This PDF is already in your library." });
  });

  it("handles 204 responses", async () => {
    mockFetch(204, undefined);
    await expect(api.deleteDocument("d1")).resolves.toBeUndefined();
  });

  it("reports network failures clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.dashboard()).rejects.toMatchObject({ code: "network_error" });
  });

  it("encodes identifiers in paths", async () => {
    const fetch = mockFetch(200, {});
    await api.getDocument("../../etc");
    expect(fetch.mock.calls[0][0]).toBe("/api/backend/documents/..%2F..%2Fetc");
  });
});

describe("verify form validation", () => {
  const valid = { claim_text: "Dropout reduces overfitting.", title: "", research_context: "", document_ids: ["d1"], top_k: 8 };

  it("accepts a valid submission", () => {
    expect(verifySchema.safeParse(valid).success).toBe(true);
  });

  it.each([
    [{ claim_text: "  hi " }, "claim_text"],
    [{ claim_text: "x".repeat(2001) }, "claim_text"],
    [{ document_ids: [] }, "document_ids"],
    [{ top_k: 2 }, "top_k"],
    [{ top_k: 21 }, "top_k"],
  ])("rejects %o", (patch, field) => {
    const result = verifySchema.safeParse({ ...valid, ...patch });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0].path[0]).toBe(field);
  });
});
