import pymupdf
import pytest

from app.core.errors import PayloadTooLargeError, ValidationFailed
from app.services.pdf_extraction_service import extract_pdf, validate_pdf
from tests.pdf_factory import DROPOUT_SUPPORT, make_pdf

MB = 1024 * 1024


def validate(data: bytes, name: str = "a.pdf", mime: str | None = "application/pdf", max_bytes: int = 5 * MB, max_pages: int = 50):
    return validate_pdf(data, name, mime, max_bytes=max_bytes, max_pages=max_pages)


class TestValidation:
    def test_valid_pdf_returns_page_count(self):
        assert validate(make_pdf(DROPOUT_SUPPORT)) == 3

    @pytest.mark.parametrize("name", ["paper.txt", "paper.pdf.exe", "", "paper"])
    def test_rejects_wrong_extension(self, name):
        with pytest.raises(ValidationFailed) as exc:
            validate(make_pdf(DROPOUT_SUPPORT), name=name)
        assert exc.value.code == "invalid_file_type"

    def test_rejects_non_pdf_content_with_pdf_name(self):
        with pytest.raises(ValidationFailed) as exc:
            validate(b"<html><body>not a pdf</body></html>", name="fake.pdf")
        assert exc.value.code == "invalid_file_type"

    def test_rejects_declared_non_pdf_mime(self):
        with pytest.raises(ValidationFailed):
            validate(make_pdf(DROPOUT_SUPPORT), mime="text/html")

    def test_accepts_octet_stream_mime_because_content_is_checked(self):
        assert validate(make_pdf(DROPOUT_SUPPORT), mime="application/octet-stream") == 3

    def test_rejects_empty_file(self):
        with pytest.raises(ValidationFailed) as exc:
            validate(b"")
        assert exc.value.code == "empty_file"

    def test_rejects_oversized_file(self):
        with pytest.raises(PayloadTooLargeError):
            validate(make_pdf(DROPOUT_SUPPORT), max_bytes=100)

    def test_rejects_malformed_pdf(self):
        with pytest.raises(ValidationFailed) as exc:
            validate(b"%PDF-1.7\n" + b"\x00garbage" * 50)
        assert exc.value.code in {"unreadable_pdf", "empty_pdf"}

    def test_rejects_too_many_pages(self):
        with pytest.raises(ValidationFailed) as exc:
            validate(make_pdf(DROPOUT_SUPPORT), max_pages=2)
        assert exc.value.code == "too_many_pages"

    def test_rejects_encrypted_pdf(self):
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "secret")
        data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
        with pytest.raises(ValidationFailed) as exc:
            validate(data)
        assert exc.value.code == "encrypted_pdf"


class TestExtraction:
    def test_pages_are_physical_and_one_based(self):
        result = extract_pdf(make_pdf(DROPOUT_SUPPORT), ocr_min_chars_per_page=50)
        assert result.page_count == 3
        assert [p.page_number for p in result.pages] == [1, 2, 3]
        assert "reduced overfitting" in " ".join(b.text for b in result.pages[1].blocks)
        assert result.page_labels is None  # no labels defined -> none invented

    def test_page_labels_are_preserved_when_defined(self):
        result = extract_pdf(make_pdf(DROPOUT_SUPPORT, roman_labels=True), ocr_min_chars_per_page=50)
        assert result.page_labels == ["i", "ii", "iii"]

    def test_headings_are_detected(self):
        result = extract_pdf(make_pdf(DROPOUT_SUPPORT), ocr_min_chars_per_page=50)
        headings = [b.text for p in result.pages for b in p.blocks if b.is_heading]
        assert "1 Introduction" in headings and "4 Results" in headings

    def test_reference_list_is_excluded_and_reported(self):
        result = extract_pdf(make_pdf(DROPOUT_SUPPORT), ocr_min_chars_per_page=50)
        assert result.reference_pages == [3]
        assert result.pages[2].blocks == []
        assert any("Reference list detected" in w for w in result.warnings)

    def test_metadata_from_pdf_info(self):
        pdf = make_pdf(DROPOUT_SUPPORT, title="Dropout in Practice", author="Ada Lovelace; Alan Turing")
        result = extract_pdf(pdf, ocr_min_chars_per_page=50)
        assert result.metadata["title"] == "Dropout in Practice"
        assert result.metadata["authors"] == ["Ada Lovelace", "Alan Turing"]
        assert result.metadata_sources["title"] == "pdf_metadata"

    def test_doi_and_year_patterns(self):
        pages = [[("p", "Published: 12 March 2021. https://doi.org/10.1234/abcd.5678. Some body text follows here.")]]
        result = extract_pdf(make_pdf(pages), ocr_min_chars_per_page=10)
        assert result.metadata["doi"] == "10.1234/abcd.5678"
        assert result.metadata["publication_year"] == 2021
        assert result.metadata_sources["publication_year"] == "text_pattern"

    def test_no_year_is_invented(self):
        result = extract_pdf(make_pdf(DROPOUT_SUPPORT), ocr_min_chars_per_page=50)
        assert "publication_year" not in result.metadata
        assert "doi" not in result.metadata

    def test_scanned_document_needs_ocr(self):
        result = extract_pdf(make_pdf([], blank_pages=3), ocr_min_chars_per_page=50)
        assert result.needs_ocr
        assert any("OCR" in w for w in result.warnings)

    def test_partially_empty_pages_are_reported(self):
        result = extract_pdf(make_pdf(DROPOUT_SUPPORT[:2], blank_pages=1), ocr_min_chars_per_page=20)
        assert not result.needs_ocr
        assert any("page(s) 3" in w for w in result.warnings)
