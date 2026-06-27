from __future__ import annotations

import pytest
from pypdf import PdfReader
from tests.helpers import OCR_FIXTURES_DIR, OCR_IMAGE_FIXTURE, OCR_PDF_FIXTURE

from srxy import magic_file_search
from srxy.ocr_text import iter_image_ocr_lines, ocr_pdf_page_images, tesseract_available


pytestmark = [pytest.mark.integration, pytest.mark.ocr]

_requires_tesseract = pytest.mark.skipif(
	not tesseract_available(),
	reason="tesseract binary not on PATH",
)


@_requires_tesseract
def test_given_ocr_image_fixture_when_searching_with_ocr_then_finds_revenue():
	# when
	results = magic_file_search(OCR_FIXTURES_DIR, "revenue", ocr=True, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path == OCR_IMAGE_FIXTURE
	assert any(line.location_kind == "ocr" for line in results[0].lines)
	assert any("revenue" in line.text.lower() for line in results[0].lines)


@_requires_tesseract
def test_given_ocr_pdf_fixture_when_searching_with_ocr_then_finds_classifier():
	# when
	results = magic_file_search(OCR_FIXTURES_DIR, "classifier", ocr=True, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path == OCR_PDF_FIXTURE
	assert any(line.line_number == 1 for line in results[0].lines)
	assert any("classifier" in line.text.lower() for line in results[0].lines)


@_requires_tesseract
def test_given_ocr_pdf_fixture_when_extracting_embedded_image_text_then_reads_classifier():
	# given
	page = PdfReader(str(OCR_PDF_FIXTURE)).pages[0]

	# when
	text = ocr_pdf_page_images(page)

	# then
	assert "classifier" in text.lower()


@_requires_tesseract
def test_given_ocr_image_fixture_when_iterating_lines_then_reads_revenue():
	# when
	lines = list(iter_image_ocr_lines(OCR_IMAGE_FIXTURE))

	# then
	assert lines
	assert any("revenue" in line_text.lower() for _, line_text in lines)
