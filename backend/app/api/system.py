from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app import __version__
from app.api.deps import get_container, get_current_user
from app.api.documents import to_out as document_out
from app.core.config import METHODOLOGY_VERSION
from app.core.container import Container
from app.core.errors import AppError
from app.core.security import AuthUser
from app.schemas.api import CurrentUser, DashboardOut, HealthResponse, ModelCheckResponse, SystemStatus
from app.services.prompts import PROMPT_VERSION

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe. Does not touch external services."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/api/v1/system/status", response_model=SystemStatus)
def system_status(container: Container = Depends(get_container)) -> SystemStatus:
    """Non-secret configuration summary used by the UI to label local/dev modes honestly."""
    s = container.settings
    try:
        container.repo.ping()
        database_ok = True
    except Exception:
        database_ok = False
    return SystemStatus(
        app_env=s.app_env,
        auth_mode=container.authenticator.mode,  # type: ignore[arg-type]
        database_backend=container.repo.dialect,  # type: ignore[arg-type]
        storage_backend=container.storage.backend,  # type: ignore[arg-type]
        embedding_provider=s.embedding_provider,
        embedding_model=container.embedder.model_id,
        embedding_dimension=container.embedder.dimension,
        assessment_configured=container.assessor.available,
        gemini_model=container.assessor.model_identifier,
        methodology_version=METHODOLOGY_VERSION,
        prompt_version=PROMPT_VERSION,
        max_upload_size_mb=s.max_upload_size_mb,
        max_pdf_pages=s.max_pdf_pages,
        database_ok=database_ok,
    )


@router.post("/api/v1/system/check-model", response_model=ModelCheckResponse)
async def check_model(
    user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> ModelCheckResponse:
    """Ask Gemini whether the configured model exists and is accessible with the configured key."""
    container.rate_limiter.check(user.id, "model check", 5)
    if container.llm is None:
        return ModelCheckResponse(ok=False, model=None, error="GOOGLE_API_KEY and GEMINI_MODEL are not configured.")
    try:
        detail = await run_in_threadpool(container.llm.check_model)
    except AppError as exc:
        return ModelCheckResponse(ok=False, model=container.llm.model_identifier, error=exc.message)
    return ModelCheckResponse(ok=True, model=container.llm.model_identifier, detail=detail)


@router.get("/api/v1/me", response_model=CurrentUser)
def me(user: AuthUser = Depends(get_current_user)) -> CurrentUser:
    return CurrentUser(id=user.id, email=user.email, auth_mode=user.auth_mode)  # type: ignore[arg-type]


@router.get("/api/v1/dashboard", response_model=DashboardOut)
def dashboard(user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)) -> DashboardOut:
    counts = container.repo.dashboard_counts(user.id)
    investigations, _ = container.repo.list_investigations(user.id, limit=5)
    reports, _ = container.reports.list(user.id, 5, 0)
    documents, _ = container.repo.list_documents(user.id, limit=5)
    return DashboardOut(
        **counts,
        recent_investigations=[container.investigations.to_out(i) for i in investigations],
        recent_reports=reports,
        recent_documents=[document_out(d) for d in documents],
    )
