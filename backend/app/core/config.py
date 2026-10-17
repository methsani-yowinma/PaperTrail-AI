"""Application configuration.

All settings come from environment variables (or `backend/.env`). Secrets are typed as
`SecretStr` so they are never rendered by `repr()`/logging. `validate_for_startup()` turns
an incomplete configuration into a readable error that names the missing variables
without ever printing their values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Bumped whenever retrieval, prompts or aggregation rules change in a way that could
# change a verdict. Stored with every assessment for reproducibility.
METHODOLOGY_VERSION = "2026.10-mvp1"

LOCAL_USER_ID = "00000000-0000-4000-8000-000000000001"


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or inconsistent."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- Auth -------------------------------------------------------------------------
    auth_mode: Literal["local", "supabase"] = "local"

    # --- Persistence ------------------------------------------------------------------
    database_backend: Literal["sqlite", "postgres"] = "sqlite"
    sqlite_path: Path = BACKEND_ROOT / "data" / "papertrail.db"
    database_url: SecretStr | None = None

    storage_backend: Literal["local", "supabase"] = "local"
    local_storage_dir: Path = BACKEND_ROOT / "data" / "uploads"

    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_storage_bucket: str = "documents"

    # --- Gemini -----------------------------------------------------------------------
    google_api_key: SecretStr | None = None
    gemini_model: str | None = None
    gemini_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    gemini_max_retries: int = Field(default=2, ge=0, le=5)

    # --- Embeddings -------------------------------------------------------------------
    embedding_provider: Literal["sentence-transformers", "hashing"] = "sentence-transformers"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = Field(default=384, gt=0)
    embedding_batch_size: int = Field(default=16, gt=0)

    # --- Ingestion --------------------------------------------------------------------
    max_upload_size_mb: int = Field(default=25, gt=0, le=200)
    max_pdf_pages: int = Field(default=300, gt=0, le=5000)
    ocr_min_chars_per_page: int = Field(default=50, ge=0)
    chunk_target_tokens: int = Field(default=450, ge=50, le=2000)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=500)

    # --- Retrieval --------------------------------------------------------------------
    retrieval_top_k: int = Field(default=8, ge=1, le=30)
    retrieval_candidates: int = Field(default=30, ge=5, le=200)
    retrieval_rrf_k: int = Field(default=60, ge=1)
    retrieval_max_per_document: int = Field(default=4, ge=1)
    # Minimum cosine similarity for a semantic-only match to count as relevant.
    # This is a model-specific heuristic, NOT a calibrated probability.
    retrieval_min_semantic_similarity: float = Field(default=0.60, ge=-1, le=1)

    # --- HTTP -------------------------------------------------------------------------
    allowed_origins: str = "http://localhost:3000"
    rate_limit_verify_per_minute: int = Field(default=10, ge=1)
    rate_limit_upload_per_minute: int = Field(default=20, ge=1)

    @field_validator("supabase_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def gemini_configured(self) -> bool:
        return bool(self.google_api_key and self.google_api_key.get_secret_value() and self.gemini_model)

    def validate_for_startup(self) -> None:
        """Fail fast with a clear message. Never includes secret values."""
        problems: list[str] = []

        if self.app_env == "production":
            if self.auth_mode != "supabase":
                problems.append("AUTH_MODE must be 'supabase' when APP_ENV=production (local mode has no authentication).")
            if self.database_backend != "postgres":
                problems.append("DATABASE_BACKEND must be 'postgres' when APP_ENV=production.")
            if self.storage_backend != "supabase":
                problems.append("STORAGE_BACKEND must be 'supabase' when APP_ENV=production.")
            if self.embedding_provider == "hashing":
                problems.append("EMBEDDING_PROVIDER=hashing is a test-only provider and is not allowed in production.")
            if "*" in self.cors_origins:
                problems.append("ALLOWED_ORIGINS must list explicit origins in production (no '*').")

        if self.auth_mode == "supabase":
            if not self.supabase_url:
                problems.append("SUPABASE_URL is required when AUTH_MODE=supabase.")
            if not self.supabase_anon_key:
                problems.append("SUPABASE_ANON_KEY is required when AUTH_MODE=supabase.")
        if self.database_backend == "postgres" and not self.database_url:
            problems.append("DATABASE_URL is required when DATABASE_BACKEND=postgres.")
        if self.storage_backend == "supabase":
            if not self.supabase_url:
                problems.append("SUPABASE_URL is required when STORAGE_BACKEND=supabase.")
            if not self.supabase_service_role_key:
                problems.append("SUPABASE_SERVICE_ROLE_KEY is required when STORAGE_BACKEND=supabase.")
        if bool(self.google_api_key) != bool(self.gemini_model):
            problems.append(
                "GOOGLE_API_KEY and GEMINI_MODEL must be set together (or both left empty to run without claim assessment)."
            )
        if self.chunk_overlap_tokens >= self.chunk_target_tokens:
            problems.append("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_TARGET_TOKENS.")

        if problems:
            raise ConfigurationError("Invalid PaperTrail AI configuration:\n  - " + "\n  - ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
