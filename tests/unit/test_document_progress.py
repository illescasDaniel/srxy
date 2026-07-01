from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from srxy.document_text import _iter_pdf_lines  # pyright: ignore[reportPrivateUsage]
from srxy.progress import ActivityUpdate


def test_given_pdf_with_ocr_when_iterating_pages_then_emits_page_progress(tmp_path: Path):
	# given
	pdf_path = tmp_path / "scan.pdf"
	pdf_path.write_bytes(b"%PDF-1.4")
	page_one = MagicMock()
	page_one.extract_text.return_value = ""
	page_one.images = {}
	page_two = MagicMock()
	page_two.extract_text.return_value = "page two"
	page_two.images = {}
	reader = MagicMock()
	reader.pages = [page_one, page_two]
	received: list[ActivityUpdate | None] = []

	# when
	with (
		patch("pypdf.PdfReader", return_value=reader),
		patch("srxy.ocr_text.ocr_pdf_page_images", return_value=""),
		patch("srxy.ocr_text.is_ocr_active", return_value=True),
		patch("srxy.ocr_text.ocr_max_file_size", return_value=None),
	):
		lines = list(_iter_pdf_lines(pdf_path, ocr=True, on_activity=received.append))

	# then
	assert lines == [(2, "page two", "page")]
	assert received == [
		ActivityUpdate(label="OCR · scan.pdf", current=1, total=2),
		ActivityUpdate(label="OCR · scan.pdf", current=2, total=2),
	]
