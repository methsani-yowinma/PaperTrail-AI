"""Wires settings, infrastructure and services together.

Tests build a container with in-memory/fake components and pass it to ``create_app``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import LOCAL_USER_ID, Settings
from app.core.security import Authenticator, LocalAuthenticator, RateLimiter, SupabaseAuthenticator
from app.repositories.base import Repository
from app.services.claim_assessment_service import ClaimAssessmentService
from app.services.document_service import DocumentService
from app.services.embedding_service import Embedder, HashingEmbedder, SentenceTransformerEmbedder
from app.services.investigation_service import InvestigationService
from app.services.llm_client import GeminiClient, LLMClient
from app.services.report_service import ReportService
from app.services.retrieval_service import RetrievalService
from app.services.storage_service import FileStorage, LocalFileStorage, SupabaseStorage


@dataclass
class Container:
    settings: Settings
    repo: Repository
    storage: FileStorage
    embedder: Embedder
    llm: LLMClient | None
    authenticator: Authenticator
    rate_limiter: RateLimiter
    documents: DocumentService
    retrieval: RetrievalService
    assessor: ClaimAssessmentService
    investigations: InvestigationService
    reports: ReportService

    def close(self) -> None:
        self.repo.close()


def build_container(
    settings: Settings,
    *,
    repo: Repository | None = None,
    storage: FileStorage | None = None,
    embedder: Embedder | None = None,
    llm: LLMClient | None = None,
    use_configured_llm: bool = True,
    authenticator: Authenticator | None = None,
) -> Container:
    if repo is None:
        if settings.database_backend == "postgres":
            from app.repositories.postgres_repository import PostgresRepository

            repo = PostgresRepository(settings.database_url.get_secret_value())  # type: ignore[union-attr]
        else:
            from app.repositories.sqlite_repository import SQLiteRepository

            repo = SQLiteRepository(settings.sqlite_path)

    if storage is None:
        if settings.storage_backend == "supabase":
            storage = SupabaseStorage(
                settings.supabase_url or "",
                settings.supabase_service_role_key.get_secret_value(),  # type: ignore[union-attr]
                settings.supabase_storage_bucket,
            )
        else:
            storage = LocalFileStorage(settings.local_storage_dir)

    if embedder is None:
        if settings.embedding_provider == "hashing":
            embedder = HashingEmbedder(settings.embedding_dimension)
        else:
            embedder = SentenceTransformerEmbedder(
                settings.embedding_model, settings.embedding_dimension, settings.embedding_batch_size
            )

    if llm is None and use_configured_llm and settings.gemini_configured:
        llm = GeminiClient(
            settings.google_api_key.get_secret_value(),  # type: ignore[union-attr]
            settings.gemini_model or "",
            timeout_seconds=settings.gemini_timeout_seconds,
            max_retries=settings.gemini_max_retries,
        )

    if authenticator is None:
        if settings.auth_mode == "supabase":
            authenticator = SupabaseAuthenticator(
                settings.supabase_url or "", settings.supabase_anon_key.get_secret_value()  # type: ignore[union-attr]
            )
        else:
            authenticator = LocalAuthenticator()
            repo.ensure_profile(LOCAL_USER_ID, "Local developer")

    retrieval = RetrievalService(settings, repo, embedder)
    assessor = ClaimAssessmentService(llm)
    investigations = InvestigationService(settings, repo, retrieval, assessor)
    return Container(
        settings=settings,
        repo=repo,
        storage=storage,
        embedder=embedder,
        llm=llm,
        authenticator=authenticator,
        rate_limiter=RateLimiter(),
        documents=DocumentService(settings, repo, storage, embedder),
        retrieval=retrieval,
        assessor=assessor,
        investigations=investigations,
        reports=ReportService(repo, investigations),
    )
