// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({ cookies: async () => ({ getAll: () => [], set: () => undefined }) }));

const { GET, POST } = await import("@/app/api/backend/[...path]/route");

function ctx(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("/api/backend proxy route", () => {
  it("forwards to the versioned FastAPI path with query string and safe headers only", async () => {
    const upstream = vi.fn().mockResolvedValue(
      new Response('{"ok":true}', { status: 200, headers: { "content-type": "application/json", "set-cookie": "x=1", "x-request-id": "abc" } }),
    );
    vi.stubGlobal("fetch", upstream);
    const request = new NextRequest("http://localhost:3000/api/backend/documents?q=dropout", {
      headers: { cookie: "sb-session=secret", "x-request-id": "req-12345678", "x-forwarded-host": "evil" },
    });
    const response = await GET(request, ctx(["documents"]));
    const [url, init] = upstream.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/documents?q=dropout");
    const sent = init.headers as Headers;
    expect(sent.get("cookie")).toBeNull();
    expect(sent.get("x-forwarded-host")).toBeNull();
    expect(sent.get("x-request-id")).toBe("req-12345678");
    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(response.headers.get("x-request-id")).toBe("abc");
  });

  it.each([[[".."]], [["documents", ".."]], [["a b"]], [[]]])("rejects unsafe path %j", async (path) => {
    vi.stubGlobal("fetch", vi.fn());
    const response = await GET(new NextRequest("http://localhost:3000/api/backend/x"), ctx(path));
    expect(response.status).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("returns a clear 502 when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("connect ECONNREFUSED")));
    const response = await POST(new NextRequest("http://localhost:3000/api/backend/investigations", { method: "POST", body: "{}" }), ctx(["investigations"]));
    expect(response.status).toBe(502);
    expect((await response.json()).error.code).toBe("backend_unreachable");
  });

  it("does not attach credentials in local mode", async () => {
    const upstream = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", upstream);
    await GET(new NextRequest("http://localhost:3000/api/backend/dashboard"), ctx(["dashboard"]));
    expect((upstream.mock.calls[0][1].headers as Headers).get("authorization")).toBeNull();
  });
});
