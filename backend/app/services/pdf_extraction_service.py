"""PDF validation, page-aware text extraction and conservative metadata extraction (PyMuPDF).

Design rules:
* Never trust the file extension or browser MIME type alone — the bytes must be a PDF that
  PyMuPDF can open.
* Page numbers are physical 1-based indexes. PDF page *labels* (e.g. "iv", "312") are stored
  separately when the file defines them; nothing is invented.
* Metadata is only filled when it can be read from the PDF's own metadata or matched by a
  strict pattern; every extracted field records its source so the UI can ask the user to
  verify uncertain values.
* No OCR is performed. Documents without an extractable text layer are flagged `needs_ocr`.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

import pymupdf

from app.core.errors import PayloadTooLargeError, ValidationFailed

ALLOWED_DECLARED_MIME = {"application/pdf", "application/x-pdf", "application/octet-stream", "binary/octet-stream", ""}
DOI_PATTERN = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
YEAR_PATTERNS = [
    re.compile(r"(?:©|\(c\)|copyright)\s*((?:19|20)\d{2})", re.IGNORECASE),
    re.compile(r"\b(?:published|accepted)(?: online)?\s*(?:on\s*)?:?\s*(?:\d{1,2}\s+)?[A-Za-z]*\.?\s*(?:\d{1,2},?\s*)?((?:19|20)\d{2})", re.IGNORECASE),
]
NUMBERED_HEADING = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2}){0,3}\.?|[IVX]{1,5}\.)\s+[A-Z][^\n]{1,100}$")
KNOWN_HEADINGS = {
    "abstract", "introduction", "background", "related work", "method", "methods", "methodology",
    "materials and methods", "experiments", "experimental setup", "results", "discussion", "conclusion",
    "conclusions", "limitations", "acknowledgements", "acknowledgments", "references", "bibliography",
    "appendix", "evaluation", "results and discussion", "future work",
}
REFERENCE_HEADINGS = {"references", "bibliography", "works cited", "literature cited"}
BAD_METADATA_TITLES = re.compile(r"^(untitled|title|microsoft word|document\d*|slide \d+)|\.(docx?|pdf|tex|dvi)$", re.IGNORECASE)


@dataclass
class TextBlock:
    text: str
    is_heading: bool = False


@dataclass
class PageText:
    page_number: int  # physical, 1-based
    label: str | None
    blocks: list[TextBlock]

    @property
    def char_count(self) -> int:
        return sum(len(b.text) for b in self.blocks)


@dataclass
class ExtractionResult:
    page_count: int
    pages: list[PageText]
    page_labels: list[str] | None
    metadata: dict[str, object]
    metadata_sources: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    needs_ocr: bool = False
    reference_pages: list[int] = field(default_factory=list)


def validate_pdf(data: bytes, filename: str, declared_mime: str | None, *, max_bytes: int, max_pages: int) -> int:
    """Validate an upload and return its page count. Raises a user-readable error otherwise."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise ValidationFailed("Only PDF files are supported (the file name must end in .pdf).", code="invalid_file_type")
    if (declared_mime or "").split(";")[0].strip().lower() not in ALLOWED_DECLARED_MIME:
        raise ValidationFailed("The file was not sent as a PDF.", code="invalid_file_type")
    if len(data) == 0:
        raise ValidationFailed("The file is empty.", code="empty_file")
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"The file is larger than the {max_bytes // (1024 * 1024)} MB upload limit.")
    # PDF header must appear within the first 1024 bytes (per the PDF specification's
    # tolerance); this rejects renamed HTML/ZIP/image files before parsing.
    if b"%PDF-" not in data[:1024]:
        raise ValidationFailed("The file content is not a PDF.", code="invalid_file_type")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several internal error types
        raise ValidationFailed("The PDF is damaged or cannot be read.", code="unreadable_pdf") from exc
    with doc:
        if doc.needs_pass or doc.is_encrypted:
            raise ValidationFailed("Password-protected PDFs are not supported.", code="encrypted_pdf")
        if doc.page_count == 0:
            raise ValidationFailed("The PDF has no pages.", code="empty_pdf")
        if doc.page_count > max_pages:
            raise ValidationFailed(f"The PDF has {doc.page_count} pages; the limit is {max_pages}.", code="too_many_pages")
        return doc.page_count


def _clean(text: str) -> str:
    text = text.replace("­", "")  # soft hyphen
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # de-hyphenate line breaks
    text = text.replace("\n", " ")
    return re.sub(r"[ \t ]+", " ", text).strip()


def _block_text_and_size(block: dict) -> tuple[str, float, bool]:
    lines, sizes, bold_chars, total_chars = [], [], 0, 0
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        lines.append("".join(s.get("text", "") for s in spans))
        for s in spans:
            n = len(s.get("text", "").strip())
            if n:
                sizes.append(float(s.get("size", 0)))
                total_chars += n
                if "bold" in str(s.get("font", "")).lower() or int(s.get("flags", 0)) & 16:
                    bold_chars += n
    text = _clean("\n".join(lines))
    size = max(sizes) if sizes else 0.0
    is_bold = total_chars > 0 and bold_chars / total_chars > 0.8
    return text, size, is_bold


def _looks_like_heading(text: str, size: float, bold: bool, body_size: float) -> bool:
    if not text or len(text) > 120 or (text.endswith((".", ",", ";")) and not NUMBERED_HEADING.match(text)):
        return False
    normalized = re.sub(r"^[\dIVX.\s]+", "", text).strip().lower()
    if normalized in KNOWN_HEADINGS and (bold or size >= body_size * 1.05 or text.isupper() or NUMBERED_HEADING.match(text)):
        return True
    if NUMBERED_HEADING.match(text) and (bold or size >= body_size * 1.1):
        return True
    return size >= body_size * 1.25 and len(text.split()) <= 14


def _split_authors(raw: str) -> list[str]:
    parts = re.split(r";|\band\b|&|,(?=\s*[A-Z][a-z]+\s+[A-Z])", raw)
    names = [p.strip(" ,") for p in parts if p and p.strip(" ,")]
    return [n for n in names if 2 <= len(n) <= 100][:50]


def extract_pdf(data: bytes, *, ocr_min_chars_per_page: int) -> ExtractionResult:
    warnings: list[str] = []
    doc = pymupdf.open(stream=data, filetype="pdf")
    with doc:
        raw_pages: list[tuple[int, str | None, list[tuple[str, float, bool]]]] = []
        sizes: list[float] = []
        labels: list[str] = []
        empty_pages: list[int] = []
        for index, page in enumerate(doc):
            label = page.get_label() if hasattr(page, "get_label") else ""
            labels.append(label or "")
            info = page.get_text("dict", sort=True)
            blocks = []
            for block in info.get("blocks", []):
                if block.get("type") != 0:  # 0 = text; images are ignored
                    continue
                text, size, bold = _block_text_and_size(block)
                if text:
                    blocks.append((text, size, bold))
                    sizes.extend([size] * min(len(text), 2000))
            if sum(len(b[0]) for b in blocks) < 20:
                empty_pages.append(index + 1)
            raw_pages.append((index + 1, label or None, blocks))

        body_size = statistics.median(sizes) if sizes else 10.0
        pages: list[PageText] = []
        in_references = False
        reference_pages: list[int] = []
        for number, label, blocks in raw_pages:
            page_blocks: list[TextBlock] = []
            for text, size, bold in blocks:
                heading = _looks_like_heading(text, size, bold, body_size)
                if heading:
                    in_references = re.sub(r"^[\dIVX.\s]+", "", text).strip().lower() in REFERENCE_HEADINGS
                if in_references:
                    if number not in reference_pages:
                        reference_pages.append(number)
                    continue
                page_blocks.append(TextBlock(text, heading))
            pages.append(PageText(number, label, page_blocks))

        page_count = doc.page_count
        total_chars = sum(len(text) for _, _, blocks in raw_pages for text, _, _ in blocks)
        needs_ocr = page_count > 0 and (total_chars / page_count) < ocr_min_chars_per_page
        if needs_ocr:
            warnings.append(
                "Little or no extractable text was found. The PDF is probably scanned; OCR is required and is not "
                "performed by this version."
            )
        elif empty_pages:
            shown = ", ".join(map(str, empty_pages[:15])) + (" …" if len(empty_pages) > 15 else "")
            warnings.append(f"No extractable text on page(s) {shown}; these pages may be images and are not searchable.")
        if reference_pages:
            warnings.append(
                f"Reference list detected (page {reference_pages[0]}"
                + (f"–{reference_pages[-1]}" if len(reference_pages) > 1 else "")
                + "); it is not indexed as evidence."
            )

        page_labels = labels if any(lbl and lbl != str(i + 1) for i, lbl in enumerate(labels)) else None

        metadata: dict[str, object] = {}
        sources: dict[str, str] = {}
        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip()
        if 5 <= len(title) <= 300 and not BAD_METADATA_TITLES.search(title):
            metadata["title"], sources["title"] = title, "pdf_metadata"
        elif raw_pages and raw_pages[0][2]:
            first = [b for b in raw_pages[0][2] if 10 <= len(b[0]) <= 250]
            if first:
                candidate = max(first, key=lambda b: b[1])
                if candidate[1] >= body_size * 1.2:
                    metadata["title"], sources["title"] = candidate[0], "first_page_layout"
                    warnings.append("The title was inferred from the first page layout. Please verify it.")
        author = (meta.get("author") or "").strip()
        if author and len(author) <= 1000:
            names = _split_authors(author)
            if names:
                metadata["authors"], sources["authors"] = names, "pdf_metadata"

        front_text = " ".join(" ".join(t for t, _, _ in blocks) for _, _, blocks in raw_pages[:2])
        doi_source = " ".join([meta.get("subject") or "", meta.get("keywords") or "", front_text])
        doi_match = DOI_PATTERN.search(doi_source)
        if doi_match:
            metadata["doi"], sources["doi"] = doi_match.group(1).rstrip(".,;)]"), "text_pattern"
        first_page = " ".join(t for t, _, _ in raw_pages[0][2]) if raw_pages else ""
        for pattern in YEAR_PATTERNS:
            year_match = pattern.search(first_page)
            if year_match:
                metadata["publication_year"], sources["publication_year"] = int(year_match.group(1)), "text_pattern"
                warnings.append("The publication year was matched from first-page text. Please verify it.")
                break

    return ExtractionResult(
        page_count=page_count,
        pages=pages,
        page_labels=page_labels,
        metadata=metadata,
        metadata_sources=sources,
        warnings=warnings,
        needs_ocr=needs_ocr,
        reference_pages=reference_pages,
    )
