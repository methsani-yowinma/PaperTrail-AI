/**
 * TypeScript mirror of the FastAPI contract in backend/app/schemas/api.py.
 * Keep the two in sync; docs/API.md documents each endpoint.
 */

export type ProcessingStatus = "pending" | "processing" | "completed" | "failed" | "needs_ocr";
export type InvestigationStatus = "draft" | "running" | "completed" | "failed";
export type Verdict = "SUPPORTED" | "CONTRADICTED" | "MIXED_EVIDENCE" | "INCONCLUSIVE";
export type PassageRelation = "SUPPORTS" | "CONTRADICTS" | "MIXED" | "NOT_RELEVANT" | "UNASSESSED";
export type Directness = "DIRECT" | "INDIRECT";
export type EvidenceStrength = "STRONG" | "MODERATE" | "WEAK";
export type EvidenceType =
  | "EXPERIMENTAL_RESULT"
  | "AUTHOR_CONCLUSION"
  | "CITED_PRIOR_WORK"
  | "BACKGROUND_MENTION"
  | "OTHER";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface SystemStatus {
  app_env: string;
  auth_mode: "local" | "supabase";
  database_backend: "sqlite" | "postgres";
  storage_backend: "local" | "supabase";
  embedding_provider: string;
  embedding_model: string;
  embedding_dimension: number;
  assessment_configured: boolean;
  gemini_model: string | null;
  methodology_version: string;
  prompt_version: string;
  max_upload_size_mb: number;
  max_pdf_pages: number;
  database_ok: boolean;
}

export interface ModelCheck {
  ok: boolean;
  model: string | null;
  detail: Record<string, unknown> | null;
  error: string | null;
}

export interface DocumentItem {
  id: string;
  original_filename: string;
  title: string | null;
  authors: string[];
  publication_year: number | null;
  doi: string | null;
  source_url: string | null;
  file_size_bytes: number;
  page_count: number | null;
  page_labels: string[] | null;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  extraction_warnings: string[];
  metadata_sources: Record<string, string>;
  embedding_model: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentUpdate {
  title?: string | null;
  authors?: string[] | null;
  publication_year?: number | null;
  doi?: string | null;
  source_url?: string | null;
}

export interface Chunk {
  id: string;
  chunk_index: number;
  page_start: number;
  page_end: number;
  page_label: string | null;
  section_title: string | null;
  content: string;
  token_count: number;
}

export interface DocumentRef {
  id: string;
  title: string | null;
  original_filename: string;
  authors: string[];
  publication_year: number | null;
  processing_status: ProcessingStatus;
}

export interface AssessmentSummary {
  id: string;
  status: "completed" | "failed";
  verdict: Verdict | null;
  created_at: string;
  error_message: string | null;
}

export interface Investigation {
  id: string;
  title: string;
  claim_text: string;
  research_context: string | null;
  status: InvestigationStatus;
  overall_verdict: Verdict | null;
  methodology_version: string;
  settings: { top_k?: number };
  last_error: string | null;
  documents: DocumentRef[];
  missing_document_count: number;
  latest_assessment: AssessmentSummary | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationCreate {
  title?: string;
  claim_text: string;
  research_context?: string;
  document_ids: string[];
  settings?: { top_k: number };
}

export interface RetrievalInfo {
  method: string;
  rank: number;
  keyword_rank: number | null;
  semantic_rank: number | null;
  fused_score: number;
  semantic_similarity: number | null;
}

export interface Citation {
  valid: boolean;
  issues: string[];
  document_id: string | null;
  chunk_id: string | null;
  document_title: string | null;
  original_filename: string | null;
  authors: string[];
  publication_year: number | null;
  doi: string | null;
  page_start: number | null;
  page_end: number | null;
  page_label: string | null;
  section_title: string | null;
  passage_text: string | null;
  excerpt_start: number | null;
  excerpt_end: number | null;
  excerpt_verified: boolean;
  excerpt_text: string | null;
  reference: string | null;
}

export interface Evidence {
  id: string;
  label: string;
  relation: PassageRelation;
  directness: Directness | null;
  evidence_strength: EvidenceStrength | null;
  evidence_type: EvidenceType | null;
  model_confidence: number | null;
  rationale: string | null;
  limitations: string[];
  retrieval: RetrievalInfo;
  citation: Citation;
}

export interface EvidenceSummary {
  retrieved_passages?: number;
  usable_assessments?: number;
  relevant_passages?: number;
  decisive_passages?: number;
  passages_by_relation?: Partial<Record<PassageRelation, number>>;
  independent_sources?: { supporting: number; contradicting: number; mixed: number; all_relevant: number };
  directness?: Partial<Record<Directness, number>>;
  strength?: Partial<Record<EvidenceStrength, number>>;
}

export interface Assessment {
  id: string;
  investigation_id: string;
  status: "completed" | "failed";
  verdict: Verdict | null;
  explanation: string | null;
  explanation_source: "model" | "template" | null;
  limitations: string[];
  reasons: string[];
  evidence_summary: EvidenceSummary;
  model_identifier: string | null;
  prompt_version: string | null;
  methodology_version: string | null;
  retrieval_configuration: Record<string, unknown>;
  metadata: {
    llm_calls?: number;
    timings_seconds?: Record<string, number>;
    retrieval_diagnostics?: Record<string, unknown>;
    error_code?: string;
  };
  error_message: string | null;
  created_at: string;
  evidence: Evidence[];
}

export interface VerifyResponse {
  investigation: Investigation;
  assessment: Assessment;
}

export interface ReportListItem {
  id: string;
  investigation_id: string;
  investigation_title: string;
  claim_text: string;
  verdict: Verdict | null;
  created_at: string;
}

export interface ReportSource {
  document_id: string;
  title: string | null;
  original_filename: string;
  authors: string[];
  publication_year: number | null;
  doi: string | null;
  page_count: number | null;
}

export interface Report {
  id: string;
  investigation_id: string;
  title: string;
  claim_text: string;
  research_context: string | null;
  verdict: Verdict;
  explanation: string | null;
  explanation_source: "model" | "template" | null;
  reasons: string[];
  evidence_summary: EvidenceSummary;
  sources: ReportSource[];
  supporting: Evidence[];
  contradicting: Evidence[];
  mixed: Evidence[];
  not_relevant: Evidence[];
  unassessed: Evidence[];
  methodology: string[];
  limitations: string[];
  model_identifier: string | null;
  prompt_version: string | null;
  methodology_version: string | null;
  retrieval_configuration: Record<string, unknown>;
  assessed_at: string;
  generated_at: string;
}

export interface Dashboard {
  documents_total: number;
  documents_by_status: Partial<Record<ProcessingStatus, number>>;
  investigations_total: number;
  reports_total: number;
  recent_investigations: Investigation[];
  recent_reports: ReportListItem[];
  recent_documents: DocumentItem[];
}

export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string | null; details?: Record<string, unknown> };
}
