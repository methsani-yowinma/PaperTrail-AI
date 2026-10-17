from datetime import datetime, timezone

from app.models.records import ChunkRecord, DocumentRecord
from app.services.citation_validation_service import anchor_quote, validate_citation

NOW = datetime.now(timezone.utc)
OWNER = "owner-1"
TEXT = "In our experiments, applying dropout with rate 0.5 reduced overfitting — the gap fell to 3.1 points."


def doc(**kw) -> DocumentRecord:
    base = dict(id="doc-1", owner_id=OWNER, original_filename="a.pdf", storage_path="x", file_hash="0" * 64,
                file_size_bytes=10, page_count=5, created_at=NOW, updated_at=NOW)
    base.update(kw)
    return DocumentRecord(**base)


def chunk(**kw) -> ChunkRecord:
    base = dict(id="c-1", document_id="doc-1", owner_id=OWNER, chunk_index=0, page_start=2, page_end=2,
                content=TEXT, content_hash="h", token_count=20, embedding_model="m", created_at=NOW)
    base.update(kw)
    return ChunkRecord(**base)


def check(**kw):
    args = dict(owner_id=OWNER, selected_document_ids={"doc-1"}, chunk=chunk(), document=doc(), quote=None)
    args.update(kw)
    return validate_citation(**args)


def test_valid_citation_with_exact_quote_is_anchored():
    result = check(quote="applying dropout with rate 0.5 reduced overfitting")
    assert result.valid and result.excerpt_verified
    assert TEXT[result.excerpt_start:result.excerpt_end] == "applying dropout with rate 0.5 reduced overfitting"


def test_quote_with_normalised_punctuation_and_spacing_is_anchored_to_original_text():
    result = check(quote="reduced   overfitting - the gap fell")
    assert result.excerpt_verified
    assert TEXT[result.excerpt_start:result.excerpt_end] == "reduced overfitting — the gap fell"


def test_fabricated_quote_is_not_verified_but_citation_still_resolves():
    result = check(quote="dropout always eliminates overfitting entirely")
    assert result.valid and not result.excerpt_verified
    assert result.excerpt_start is None
    assert "could not be found" in result.issues[0]


def test_ellipsis_quote_anchors_longest_segment():
    start, end = anchor_quote(TEXT, "applying dropout with rate 0.5 ... the gap fell")
    assert TEXT[start:end] == "applying dropout with rate 0.5"


def test_too_short_quote_is_not_anchored():
    assert anchor_quote(TEXT, "the") is None


def test_missing_chunk_is_invalid():
    assert not check(chunk=None).valid


def test_chunk_of_other_user_is_invalid():
    assert not check(chunk=chunk(owner_id="someone-else")).valid


def test_document_of_other_user_is_invalid():
    assert not check(document=doc(owner_id="someone-else")).valid


def test_chunk_from_different_document_is_invalid():
    assert not check(chunk=chunk(document_id="doc-2")).valid


def test_unselected_document_is_invalid():
    result = check(selected_document_ids={"doc-9"})
    assert not result.valid and "not selected" in result.issues[0]


def test_page_outside_document_is_invalid():
    assert not check(chunk=chunk(page_start=6, page_end=6)).valid
    assert not check(document=doc(page_count=None)).valid
