from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from tests.helpers import OCR_IMAGE_FIXTURE, write_docx_with_image, write_pptx_with_image

from srxy.document_text import (
	_document_cache_variant,  # pyright: ignore[reportPrivateUsage]
	_iter_docx_lines,  # pyright: ignore[reportPrivateUsage]
	_iter_pptx_lines,  # pyright: ignore[reportPrivateUsage]
)
from srxy.progress import ActivityUpdate


pytestmark = pytest.mark.unit


def test_given_office_suffix_when_cache_variant_with_ocr_then_includes_ocr_flag():
	# when
	with patch("srxy.ocr_text.is_ocr_active", return_value=True):
		docx_variant = _document_cache_variant(Path("memo.docx"), ocr=True)
		xlsx_variant = _document_cache_variant(Path("budget.xlsx"), ocr=True)

	# then
	assert docx_variant == ".docx:ocr=1"
	assert xlsx_variant == ".xlsx:ocr=1"


def test_given_docx_with_embedded_image_when_iterating_with_ocr_then_emits_image_progress(tmp_path: Path):
	# given
	docx_path = tmp_path / "memo.docx"
	write_docx_with_image(docx_path, OCR_IMAGE_FIXTURE)
	received: list[ActivityUpdate | None] = []

	# when
	with (
		patch("srxy.ocr_text.is_ocr_active", return_value=True),
		patch("srxy.ocr_text.ocr_max_file_size", return_value=None),
		patch("srxy.ocr_text.ocr_image_bytes", return_value="quarterly revenue projections"),
	):
		lines = list(_iter_docx_lines(docx_path, ocr=True, on_activity=received.append))

	# then
	assert any(kind == "ocr" for _, _, kind in lines)
	assert received
	assert received[0] is not None
	assert received[0].label == "OCR · memo.docx"
	assert received[0].current == 1
	assert received[0].total == 1


def test_given_pptx_with_embedded_image_when_iterating_with_ocr_then_uses_slide_number(tmp_path: Path):
	# given
	pptx_path = tmp_path / "deck.pptx"
	write_pptx_with_image(pptx_path, OCR_IMAGE_FIXTURE, text="slide body")

	# when
	with (
		patch("srxy.ocr_text.is_ocr_active", return_value=True),
		patch("srxy.ocr_text.ocr_max_file_size", return_value=None),
		patch("srxy.ocr_text.ocr_image_bytes", return_value="quarterly revenue projections"),
	):
		lines = list(_iter_pptx_lines(pptx_path, ocr=True))

	# then
	ocr_lines = [line for line in lines if line[2] == "ocr"]
	assert len(ocr_lines) == 1
	assert ocr_lines[0][0] == 1
	assert "revenue" in ocr_lines[0][1]
