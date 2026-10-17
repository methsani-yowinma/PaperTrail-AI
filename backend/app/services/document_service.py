"""Document lifecycle: upload → validate → store → process (extract, chunk, embed, persist)."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError, StorageError, ValidationFailed
from app.models.records import DocumentRecord, NewChunk, ProcessingStatus
from app.repositories.base import Repository, utcnow
from app.services.chunking_service import chunk_pages
from app.services.embedding_service import Embedder
from app.services.pdf_extraction_service import extract_pdf, validate_pdf
from app.services.storage_service import FileStorage, object_key

logger = logging.getLogger("papertrail.documents")


class DocumentService:
    def __init__(self, settings: Settings, repo: Repository, storage: FileStorage, embedder: Embedder):
        self._settings = settings
        self._repo = repo
        self._storage = storage
        self._embedder = embedder

    # ---- upload ----------------------------------------------------------------------------
    def upload(self, owner_id: str, filename: str, declared_mime: str | None, data: bytes) -> DocumentRecord:
        safe_name = (filename or "").replace("\\", "/").split("/")[-1].strip()[:255]
        page_count = validate_pdf(
            data, safe_name, declared_mime, max_bytes=self._settings.max_upload_bytes, max_pages=self._settings.max_pdf_pages
        )
        file_hash = hashlib.sha256(data).hexdigest()
        existing = self._repo.find_document_by_hash(owner_id, file_hash)
        if existing:
            raise ConflictError(
                "This PDF is already in your library.", code="duplicate_document", details={"document_id": existing.id}
            )
        document_id = str(uuid.uuid4())
        key = object_key(owner_id, document_id)
        self._storage.save(key, data)
        now = utcnow()
        record = DocumentRecord(
            id=document_id,
            owner_id=owner_id,
            original_filename=safe_name,
            title=None,
            storage_path=key,
            file_hash=file_hash,
            file_size_bytes=len(data),
            page_count=page_count,
            processing_status=ProcessingStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        try:
            return self._repo.create_document(record)
        except ConflictError:
            # A concurrent upload of the same file won the race; don't leave an orphan file.
            self._storage.delete(key)
            raise ConflictError("This PDF is already in your library.", code="duplicate_document")
        except Exception:
            self._storage.delete(key)
            raise

    # ---- processing ------------------------------------------------------------------------
    def request_reprocess(self, owner_id: str, document_id: str) -> DocumentRecord:
        doc = self.get(owner_id, document_id)
        if doc.processing_status == ProcessingStatus.PROCESSING:
            raise ConflictError("This document is already being processed.", code="already_processing")
        self._repo.set_processing_pending(owner_id, document_id)
        return self.get(owner_id, document_id)

    def process(self, owner_id: str, document_id: str) -> None:
        """Run the full ingestion pipeline. Safe to call from a background task: all errors
        are recorded on the document instead of being raised."""
        if not self._repo.claim_document_for_processing(owner_id, document_id):
            logger.info("Document %s is already processing or does not exist; skipping", document_id)
            return
        started = time.perf_counter()
        warnings: list[str] = []
        try:
            doc = self._repo.get_document(owner_id, document_id)
            if doc is None:
                return
            data = self._storage.load(doc.storage_path)
            extraction = extract_pdf(data, ocr_min_chars_per_page=self._settings.ocr_min_chars_per_page)
            warnings.extend(extraction.warnings)

            if extraction.needs_ocr:
                self._repo.complete_processing(
                    owner_id, document_id, status=ProcessingStatus.NEEDS_OCR, error=None,
                    page_count=extraction.page_count, page_labels=extraction.page_labels, warnings=warnings,
                    metadata=extraction.metadata, metadata_sources=extraction.metadata_sources,
                    chunks=[], embedding_model=self._embedder.model_id,
                )
                return

            drafts = chunk_pages(
                extraction.pages,
                target_tokens=self._settings.chunk_target_tokens,
                overlap_tokens=self._settings.chunk_overlap_tokens,
            )
            if not drafts:
                raise ValidationFailed("No usable text passages could be extracted from this PDF.", code="no_text")
            texts = [d.content for d in drafts]
            overlong = self._embedder.count_overlong(texts)
            if overlong:
                warnings.append(
                    f"{overlong} passage(s) exceed the embedding model's input length; their embeddings cover only the "
                    "beginning of the passage. Keyword search still covers the full text."
                )
            vectors = self._embedder.embed_documents(texts)
            if any(len(v) != self._embedder.dimension for v in vectors):
                raise AppError("The embedding model returned vectors of an unexpected size.", code="embedding_error")
            chunks = [
                NewChunk(
                    chunk_index=d.chunk_index, page_start=d.page_start, page_end=d.page_end, section_title=d.section_title,
                    content=d.content, content_hash=d.content_hash, token_count=d.token_count, embedding=v,
                )
                for d, v in zip(drafts, vectors)
            ]
            self._repo.complete_processing(
                owner_id, document_id, status=ProcessingStatus.COMPLETED, error=None,
                page_count=extraction.page_count, page_labels=extraction.page_labels, warnings=warnings,
                metadata=extraction.metadata, metadata_sources=extraction.metadata_sources,
                chunks=chunks, embedding_model=self._embedder.model_id,
            )
            logger.info(
                "Processed document %s: %d pages, %d chunks in %.1fs",
                document_id, extraction.page_count, len(chunks), time.perf_counter() - started,
            )
        except AppError as exc:
            self._repo.fail_processing(owner_id, document_id, exc.message, warnings)
        except Exception:
            logger.exception("Processing failed for document %s", document_id)
            self._repo.fail_processing(
                owner_id, document_id, "Processing failed because of an internal error. Try reprocessing the document.", warnings
            )

    # ---- queries & mutations --------------------------------------------------------------
    def get(self, owner_id: str, document_id: str) -> DocumentRecord:
        doc = self._repo.get_document(owner_id, document_id)
        if doc is None:
            raise NotFoundError("Document not found.")
        return doc

    def update_metadata(self, owner_id: str, document_id: str, fields: dict[str, Any]) -> DocumentRecord:
        doc = self.get(owner_id, document_id)
        if not fields:
            return doc
        sources = dict(doc.metadata_sources)
        for key in fields:
            sources[key] = "user"
        updated = self._repo.update_document_metadata(owner_id, document_id, {**fields, "metadata_sources": sources})
        if updated is None:
            raise NotFoundError("Document not found.")
        return updated

    def load_file(self, owner_id: str, document_id: str) -> tuple[DocumentRecord, bytes]:
        doc = self.get(owner_id, document_id)
        return doc, self._storage.load(doc.storage_path)

    def delete(self, owner_id: str, document_id: str) -> None:
        doc = self.get(owner_id, document_id)
        if doc.processing_status == ProcessingStatus.PROCESSING:
            raise ConflictError("Wait for processing to finish before deleting this document.", code="already_processing")
        if not self._repo.delete_document(owner_id, document_id):
            raise NotFoundError("Document not found.")
        try:
            self._storage.delete(doc.storage_path)
        except StorageError:
            # The database record is gone, so the file is unreachable through the app. Log it
            # for manual cleanup rather than failing the user's request.
            logger.warning("Stored file for deleted document %s could not be removed", document_id)
