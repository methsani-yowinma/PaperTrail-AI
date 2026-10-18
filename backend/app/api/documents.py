from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_container, get_current_user
from app.core.container import Container
from app.core.errors import PayloadTooLargeError
from app.core.security import AuthUser
from app.models.records import DocumentRecord, ProcessingStatus
from app.schemas.api import ChunkOut, DocumentOut, DocumentUpdate, Page
from app.services.investigation_service import page_label

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def to_out(doc: DocumentRecord) -> DocumentOut:
    # storage_path, file_hash and owner_id are internal and deliberately not exposed.
    return DocumentOut.model_validate(doc.model_dump())


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentOut)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="A PDF file"),
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> DocumentOut:
    """Validate and store a PDF, then process it in the background (status starts as `pending`)."""
    container.rate_limiter.check(user.id, "upload", container.settings.rate_limit_upload_per_minute)
    limit = container.settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError(f"The file is larger than the {container.settings.max_upload_size_mb} MB upload limit.")
    # Validation, hashing and storage (an HTTP call in Supabase mode) are blocking; keep them
    # off the event loop so other requests are not stalled during an upload.
    doc = await run_in_threadpool(container.documents.upload, user.id, file.filename or "", file.content_type, data)
    background.add_task(container.documents.process, user.id, doc.id)
    return to_out(doc)


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    q: str | None = Query(default=None, max_length=200),
    status_filter: ProcessingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> Page[DocumentOut]:
    docs, total = container.repo.list_documents(user.id, query=q, status=status_filter, limit=limit, offset=offset)
    return Page(items=[to_out(d) for d in docs], total=total, limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> DocumentOut:
    return to_out(container.documents.get(user.id, document_id))


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: str,
    body: DocumentUpdate,
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> DocumentOut:
    """Correct extracted metadata. Corrected fields are marked as user-provided."""
    return to_out(container.documents.update_metadata(user.id, document_id, body.model_dump(exclude_unset=True)))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> Response:
    container.documents.delete(user.id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/process", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentOut)
def reprocess_document(
    document_id: str,
    background: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> DocumentOut:
    container.rate_limiter.check(user.id, "upload", container.settings.rate_limit_upload_per_minute)
    doc = container.documents.request_reprocess(user.id, document_id)
    background.add_task(container.documents.process, user.id, doc.id)
    return to_out(doc)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
def list_chunks(
    document_id: str,
    page: int | None = Query(default=None, ge=1),
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> list[ChunkOut]:
    doc = container.documents.get(user.id, document_id)
    return [
        ChunkOut(
            id=c.id, chunk_index=c.chunk_index, page_start=c.page_start, page_end=c.page_end,
            page_label=page_label(doc, c.page_start), section_title=c.section_title, content=c.content,
            token_count=c.token_count,
        )
        for c in container.repo.list_chunks(user.id, document_id, page)
    ]


@router.get("/{document_id}/file", response_class=Response)
def download_document_file(
    document_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> Response:
    doc, data = container.documents.load_file(user.id, document_id)
    safe_name = quote(doc.original_filename)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{safe_name}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
