/**
 * Browser-side API client. All calls go to the same-origin Next.js route handler at
 * /api/backend/*, which forwards them to FastAPI and attaches the user's access token
 * server-side. The browser never talks to Gemini and never sees backend secrets.
 */
import type {
  Assessment,
  Chunk,
  Dashboard,
  DocumentItem,
  DocumentUpdate,
  Investigation,
  InvestigationCreate,
  ModelCheck,
  Page,
  Report,
  ReportListItem,
  SystemStatus,
  VerifyResponse,
} from "@/types/api";

export const API_PREFIX = "/api/backend";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId?: string | null,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    if (body?.error?.message) {
      return new ApiError(body.error.message, response.status, body.error.code, body.error.request_id, body.error.details);
    }
  } catch {
    // fall through to a generic error
  }
  return new ApiError(`Request failed (HTTP ${response.status}).`, response.status, "http_error");
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, { ...init, cache: "no-store" });
  } catch {
    throw new ApiError("Network error: the server could not be reached.", 0, "network_error");
  }
  if (response.status === 401 && typeof window !== "undefined") {
    // A hard navigation is intentional: the session expired, so proxy.ts must run again.
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${next}`);
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  systemStatus: () => request<SystemStatus>("/system/status"),
  checkModel: () => request<ModelCheck>("/system/check-model", { method: "POST" }),
  dashboard: () => request<Dashboard>("/dashboard"),

  listDocuments: (params: { q?: string; status?: string; limit?: number; offset?: number } = {}) =>
    request<Page<DocumentItem>>(`/documents${query(params)}`),
  getDocument: (id: string) => request<DocumentItem>(`/documents/${encodeURIComponent(id)}`),
  updateDocument: (id: string, body: DocumentUpdate) =>
    request<DocumentItem>(`/documents/${encodeURIComponent(id)}`, json("PATCH", body)),
  deleteDocument: (id: string) => request<void>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  reprocessDocument: (id: string) =>
    request<DocumentItem>(`/documents/${encodeURIComponent(id)}/process`, { method: "POST" }),
  listChunks: (id: string, page?: number) =>
    request<Chunk[]>(`/documents/${encodeURIComponent(id)}/chunks${query({ page })}`),
  documentFileUrl: (id: string) => `${API_PREFIX}/documents/${encodeURIComponent(id)}/file`,

  createInvestigation: (body: InvestigationCreate) => request<Investigation>("/investigations", json("POST", body)),
  listInvestigations: (params: { q?: string; limit?: number; offset?: number } = {}) =>
    request<Page<Investigation>>(`/investigations${query(params)}`),
  getInvestigation: (id: string) => request<Investigation>(`/investigations/${encodeURIComponent(id)}`),
  deleteInvestigation: (id: string) =>
    request<void>(`/investigations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  verifyInvestigation: (id: string) =>
    request<VerifyResponse>(`/investigations/${encodeURIComponent(id)}/verify`, { method: "POST" }),
  latestEvidence: (id: string) => request<Assessment>(`/investigations/${encodeURIComponent(id)}/evidence`),

  listReports: (params: { limit?: number; offset?: number } = {}) =>
    request<Page<ReportListItem>>(`/reports${query(params)}`),
  getReport: (id: string) => request<Report>(`/reports/${encodeURIComponent(id)}`),
  reportExportUrl: (id: string, format: "markdown" | "json") =>
    `${API_PREFIX}/reports/${encodeURIComponent(id)}/export?format=${format}`,
};

/** Upload with real byte-level progress (fetch cannot report upload progress). */
export function uploadDocument(file: File, onProgress: (fraction: number) => void): Promise<DocumentItem> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    xhr.open("POST", `${API_PREFIX}/documents/upload`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onerror = () => reject(new ApiError("Network error during upload.", 0, "network_error"));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // ignore
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as DocumentItem);
        return;
      }
      const err = (body as { error?: { message: string; code: string; request_id?: string; details?: Record<string, unknown> } })?.error;
      reject(
        new ApiError(err?.message ?? `Upload failed (HTTP ${xhr.status}).`, xhr.status, err?.code ?? "http_error", err?.request_id, err?.details),
      );
    };
    xhr.send(form);
  });
}
