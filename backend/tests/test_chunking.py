from app.services.chunking_service import chunk_pages, count_tokens
from app.services.pdf_extraction_service import PageText, TextBlock, extract_pdf
from tests.pdf_factory import DROPOUT_SUPPORT, make_pdf

SENTENCE = "Dropout randomly removes units during training to reduce co-adaptation between neurons. "


def page(n: int, *blocks: tuple[str, bool]) -> PageText:
    return PageText(n, None, [TextBlock(t, h) for t, h in blocks])


def test_chunks_never_span_pages_and_keep_order():
    pages = [page(1, (SENTENCE * 30, False)), page(2, (SENTENCE * 30, False))]
    chunks = chunk_pages(pages, target_tokens=120, overlap_tokens=20)
    assert len(chunks) > 2
    assert all(c.page_start == c.page_end for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert {c.page_start for c in chunks} == {1, 2}


def test_chunk_size_respects_target():
    chunks = chunk_pages([page(1, (SENTENCE * 60, False))], target_tokens=100, overlap_tokens=10)
    # Packing stops before exceeding the target; overlap may add a sentence on top.
    assert all(c.token_count <= 100 + count_tokens(SENTENCE) for c in chunks)


def test_overlap_repeats_trailing_sentence_on_same_page():
    chunks = chunk_pages([page(1, *[(SENTENCE.strip(), False)] * 20)], target_tokens=60, overlap_tokens=20)
    assert len(chunks) >= 2
    last_sentence_of_first = chunks[0].content.split("\n\n")[-1]
    assert chunks[1].content.startswith(last_sentence_of_first)


def test_section_titles_follow_headings_across_pages():
    pages = [
        page(1, ("1 Introduction", True), (SENTENCE * 3, False), ("2 Methods", True), (SENTENCE * 3, False)),
        page(2, (SENTENCE * 3, False)),
    ]
    chunks = chunk_pages(pages, target_tokens=400, overlap_tokens=0)
    assert [c.section_title for c in chunks] == ["1 Introduction", "2 Methods", "2 Methods"]
    assert chunks[1].content.startswith("2 Methods")


def test_tiny_fragments_merge_into_previous_chunk():
    chunks = chunk_pages([page(1, (SENTENCE * 5, False), ("Fig. 1", False))], target_tokens=400, overlap_tokens=0)
    assert len(chunks) == 1
    assert chunks[0].content.endswith("Fig. 1")


def test_hash_is_deterministic():
    pages = [page(1, (SENTENCE * 5, False))]
    a = chunk_pages(pages, target_tokens=400, overlap_tokens=0)
    b = chunk_pages(pages, target_tokens=400, overlap_tokens=0)
    assert a[0].content_hash == b[0].content_hash


def test_real_pdf_chunks_carry_page_metadata():
    result = extract_pdf(make_pdf(DROPOUT_SUPPORT), ocr_min_chars_per_page=50)
    chunks = chunk_pages(result.pages, target_tokens=450, overlap_tokens=50)
    by_page = {c.page_start: c for c in chunks}
    assert "reduced overfitting" in by_page[2].content
    assert by_page[2].section_title == "4 Results"
    assert 3 not in by_page  # references page is not indexed
