from __future__ import annotations

import pytest
from PIL import Image
from tests.helpers import OCR_IMAGE_FIXTURE, OCR_PDF_FIXTURE, file_search_root, require_file_search_fixtures

from srxy.adapters.outbound.ocr.ocr_text import (
	iter_image_ocr_lines,
	ocr_pdf_page_images,
	ocr_pil_image,
	tesseract_available,
)


pytestmark = [pytest.mark.integration, pytest.mark.ocr]


@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
def test_given_cover_image_when_ocring_then_reads_embedded_text():
	# given
	require_file_search_fixtures()
	cover = file_search_root() / "cover.jpg"
	assert cover.is_file(), f"missing cover fixture: {cover}"

	# when
	with Image.open(cover) as image:
		text = ocr_pil_image(image)

	# then
	lowered = text.lower()
	assert "fixture" in lowered
	assert "composer" in lowered


@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
def test_given_ocr_image_fixture_when_running_tesseract_then_reads_revenue():
	# when
	lines = list(iter_image_ocr_lines(OCR_IMAGE_FIXTURE))

	# then
	assert lines
	assert any("revenue" in line_text.lower() for _, line_text in lines)


@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
def test_given_ocr_pdf_fixture_when_running_tesseract_then_reads_classifier():
	# given
	from pypdf import PdfReader

	page = PdfReader(str(OCR_PDF_FIXTURE)).pages[0]

	# when
	text = ocr_pdf_page_images(page)

	# then
	assert "classifier" in text.lower()
