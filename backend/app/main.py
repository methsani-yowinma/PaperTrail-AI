"""FastAPI application factory.

Run locally:  uvicorn app.main:app --reload --port 8000   (from the backend/ directory)
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import documents, investigations, reports, system
from app.core.config import Settings, get_settings
from app.core.container import Container, build_container
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging

logger = logging.getLogger("papertrail")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else get_settings())
    settings.validate_for_startup()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.container is None:
            app.state.container = build_container(settings)
        interrupted = app.state.container.repo.mark_interrupted_processing()
        if interrupted:
            logger.warning("Marked %d interrupted job(s) as failed after restart", interrupted)
        logger.info(
            "PaperTrail AI backend started (env=%s, auth=%s, db=%s, storage=%s, assessment=%s)",
            settings.app_env, settings.auth_mode, settings.database_backend, settings.storage_backend,
            "configured" if settings.gemini_configured else "NOT configured",
        )
        yield
        app.state.container.close()

    app = FastAPI(
        title="PaperTrail AI API",
        version=__version__,
        description="Evidence retrieval and claim verification over user-uploaded research documents.",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )
    app.state.container = container
    app.state.known_profiles = set()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    max_body = settings.max_upload_bytes + 1024 * 1024  # file + multipart overhead

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request.state.request_id = request_id
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_body:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "payload_too_large", "message": "The request body is too large.",
                                   "request_id": request_id}},
                headers={"X-Request-ID": request_id},
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    install_error_handlers(app)
    app.include_router(system.router)
    app.include_router(documents.router)
    app.include_router(investigations.router)
    app.include_router(reports.router)
    return app


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()
