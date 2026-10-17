"""Page-aware, section-aware chunking.

Rules (documented in docs/AI_METHODOLOGY.md):
* A chunk never spans two pages, so every passage has an exact page citation.
* A new section heading starts a new chunk; the heading text stays in the chunk content and
  is also stored as ``section_title`` (carried across pages until the next heading).
* Paragraphs are packed up to ``target_tokens``; oversized paragraphs are split at sentence
  boundaries, and oversized sentences at word boundaries.
* Adjacent chunks on the same page share up to ``overlap_tokens`` of trailing sentences.
* Token counts are an approximation (words + punctuation marks), not a model tokenizer.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.services.pdf_extraction_service import PageText

_TOKEN = re.compile(r"\w+|[^\w\s]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
MIN_CHUNK_TOKENS = 12


def count_tokens(text: str) -> int:
    return len(_TOKEN.findall(text))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class ChunkDraft:
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    content: str
    content_hash: str
    token_count: int


def _split_long(text: str, limit: int) -> list[str]:
    """Split text into pieces of at most ~limit tokens at sentence, then word, boundaries."""
    if count_tokens(text) <= limit:
        return [text]
    pieces: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        if count_tokens(sentence) <= limit:
            pieces.append(sentence)
            continue
        words, current = sentence.split(" "), []
        for word in words:
            current.append(word)
            if count_tokens(" ".join(current)) >= limit:
                pieces.append(" ".join(current))
                current = []
        if current:
            pieces.append(" ".join(current))
    return pieces


def _overlap_tail(text: str, overlap_tokens: int) -> str:
    if overlap_tokens <= 0:
        return ""
    sentences = _SENTENCE_SPLIT.split(text)
    tail: list[str] = []
    for sentence in reversed(sentences):
        if count_tokens(" ".join([sentence, *tail])) > overlap_tokens:
            break
        tail.insert(0, sentence)
    # Only reuse complete sentences; never the whole chunk.
    return " ".join(tail) if tail and len(tail) < len(sentences) else ""


def chunk_pages(pages: list[PageText], *, target_tokens: int, overlap_tokens: int) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    section: str | None = None

    def emit(page: int, parts: list[str], section_title: str | None) -> None:
        content = "\n\n".join(p for p in parts if p).strip()
        tokens = count_tokens(content)
        if tokens < MIN_CHUNK_TOKENS:
            # Too small to be useful evidence; merge into the previous chunk on the same page.
            if drafts and drafts[-1].page_end == page and content:
                prev = drafts[-1]
                merged = f"{prev.content}\n\n{content}"
                drafts[-1] = ChunkDraft(prev.chunk_index, prev.page_start, page, prev.section_title, merged,
                                        content_hash(merged), count_tokens(merged))
            return
        drafts.append(ChunkDraft(len(drafts), page, page, section_title, content, content_hash(content), tokens))

    for page in pages:
        parts: list[str] = []
        parts_tokens = 0
        chunk_section = section
        for block in page.blocks:
            if block.is_heading:
                if parts and count_tokens("\n\n".join(parts)) >= MIN_CHUNK_TOKENS:
                    emit(page.page_number, parts, chunk_section)
                    parts, parts_tokens = [], 0
                section = block.text
                chunk_section = section
                parts.append(block.text)
                parts_tokens += count_tokens(block.text)
                continue
            for piece in _split_long(block.text, target_tokens):
                piece_tokens = count_tokens(piece)
                if parts and parts_tokens + piece_tokens > target_tokens:
                    previous = "\n\n".join(parts)
                    emit(page.page_number, parts, chunk_section)
                    tail = _overlap_tail(previous, overlap_tokens)
                    parts = [tail] if tail else []
                    parts_tokens = count_tokens(tail) if tail else 0
                    chunk_section = section
                parts.append(piece)
                parts_tokens += piece_tokens
        if parts:
            emit(page.page_number, parts, chunk_section)
    return drafts
