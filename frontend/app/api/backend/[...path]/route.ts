/**
 * Same-origin gateway to the FastAPI backend.
 *
 * Browser → /api/backend/<path> → FastAPI /api/v1/<path>
 *
 * - The backend URL is server-only (API_BASE_URL), so the browser never needs CORS access.
 * - In Supabase mode the user's access token is read from the session cookie here and sent
 *   as a bearer token; FastAPI verifies it with Supabase Auth.
 * - No business logic lives here: FastAPI owns every rule.
 */
import type { NextRequest } from "next/server";

import { getServerSupabase } from "@/lib/supabase/server";

const BACKEND = (process.env.API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const FORWARD_REQUEST_HEADERS = ["content-type", "accept", "x-request-id"];
const FORWARD_RESPONSE_HEADERS = ["content-type", "content-disposition", "x-request-id", "cache-control"];
const SEGMENT = /^[A-Za-z0-9._~-]+$/;
const BEARER = /^Bearer [A-Za-z0-9._~+/=-]+$/;

type Context = { params: Promise<{ path: string[] }> };

function errorResponse(status: number, code: string, message: string) {
  return Response.json({ error: { code, message, request_id: null } }, { status });
}

async function forward(request: NextRequest, context: Context): Promise<Response> {
  const { path } = await context.params;
  if (!path.length || path.some((s) => !SEGMENT.test(s) || s === "." || s === "..")) {
    return errorResponse(400, "invalid_path", "Invalid API path.");
  }
  const target = `${BACKEND}/api/v1/${path.join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  // API clients without a browser session (e.g. scripts/smoke_test.py --token) may send their
  // own bearer token; FastAPI verifies it exactly like a session token. A session cookie wins.
  const clientAuthorization = request.headers.get("authorization");
  if (clientAuthorization && BEARER.test(clientAuthorization)) headers.set("authorization", clientAuthorization);
  const supabase = await getServerSupabase();
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) headers.set("authorization", `Bearer ${data.session.access_token}`);
  }

  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // Required by Node's fetch to stream a request body.
      ...(hasBody ? { duplex: "half" } : {}),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(300_000),
    } as RequestInit);
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    return timedOut
      ? errorResponse(504, "backend_timeout", "The analysis server took too long to respond.")
      : errorResponse(502, "backend_unreachable", "The analysis server is not reachable. Is the backend running?");
  }

  const responseHeaders = new Headers();
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
