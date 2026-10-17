"""Citation validation — independent of the LLM.

Every citation shown to a user must resolve to a stored passage of a stored document that
the user owns and selected for the investigation, with a valid page reference. Quotations
are anchored to the stored passage text by character offsets; a quotation that cannot be
found in the stored text is never displayed as a quotation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.models.records import ChunkRecord, DocumentRecord

_EQUIVALENTS = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    " ": " ",
}
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")
MIN_ANCHOR_CHARS = 12


@dataclass
class CitationCheck:
    valid: bool
    issues: list[str] = field(default_factory=list)
    excerpt_start: int | None = None
    excerpt_end: int | None = None
    excerpt_verified: bool = False


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Lower-case, unify quotes/dashes/ligatures and collapse whitespace, keeping a map from
    each normalized character back to its index in the original text."""
    out: list[str] = []
    index_map: list[int] = []
    previous_space = True
    for i, ch in enumerate(text):
        ch = _EQUIVALENTS.get(ch, ch)
        expanded = unicodedata.normalize("NFKC", ch).lower()
        for piece in expanded:
            if piece.isspace():
                if previous_space:
                    continue
                piece, previous_space = " ", True
            else:
                previous_space = False
            out.append(piece)
            index_map.append(i)
    while out and out[-1] == " ":
        out.pop()
        index_map.pop()
    return "".join(out), index_map


def anchor_quote(passage: str, quote: str) -> tuple[int, int] | None:
    """Return (start, end) offsets of ``quote`` inside ``passage`` or None if it isn't there."""
    quote = quote.strip().strip('"').strip()
    if len(quote) < MIN_ANCHOR_CHARS:
        return None
    start = passage.find(quote)
    if start >= 0:
        return start, start + len(quote)
    norm_passage, index_map = _normalize_with_map(passage)
    # If the model elided text with "...", anchor the longest contiguous segment only.
    segments = [s for s in _ELLIPSIS.split(quote) if s.strip()]
    for segment in sorted(segments, key=len, reverse=True):
        norm_quote, _ = _normalize_with_map(segment)
        if len(norm_quote) < MIN_ANCHOR_CHARS:
            continue
        pos = norm_passage.find(norm_quote)
        if pos >= 0:
            return index_map[pos], index_map[pos + len(norm_quote) - 1] + 1
    return None


def validate_citation(
    *,
    owner_id: str,
    selected_document_ids: set[str],
    chunk: ChunkRecord | None,
    document: DocumentRecord | None,
    quote: str | None,
) -> CitationCheck:
    issues: list[str] = []
    if chunk is None:
        return CitationCheck(False, ["The cited passage does not exist in the database."])
    if chunk.owner_id != owner_id:
        return CitationCheck(False, ["The cited passage does not belong to the current user."])
    if document is None:
        return CitationCheck(False, ["The cited passage's document does not exist."])
    if document.owner_id != owner_id:
        return CitationCheck(False, ["The cited document does not belong to the current user."])
    if chunk.document_id != document.id:
        return CitationCheck(False, ["The cited passage does not belong to the cited document."])
    if document.id not in selected_document_ids:
        return CitationCheck(False, ["The cited document was not selected for this investigation."])
    if document.page_count is None or not (1 <= chunk.page_start <= chunk.page_end <= document.page_count):
        return CitationCheck(False, ["The page reference is outside the document's page range."])

    check = CitationCheck(True, issues)
    if quote:
        anchored = anchor_quote(chunk.content, quote)
        if anchored:
            check.excerpt_start, check.excerpt_end = anchored
            check.excerpt_verified = True
        else:
            issues.append("The model's quotation could not be found in the stored passage, so it is not shown.")
    return check
