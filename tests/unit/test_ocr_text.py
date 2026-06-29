from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from tests.helpers import file_search_root, require_file_search_fixtures

from srxy.ocr_text import (
	DEFAULT_OCR_MAX_FILE_SIZE,
	TesseractEngine,
	ensure_ocr_available,
	is_ocr_active,
	is_ocr_available,
	is_sparse_text,
	iter_image_ocr_lines,
	ocr_max_file_size,
	ocr_pdf_page_images,
	ocr_pil_image,
	ocr_requested,
	ocr_unavailable_message,
	preprocess_image,
	reset_ocr_engine,
	tesseract_available,
)


pytestmark = pytest.mark.unit


def test_given_sparse_text_when_checking_then_returns_true():
	# given
	text = "short"

	# when / then
	assert is_sparse_text(text) is True


def test_given_rich_text_when_checking_then_returns_false():
	# given
	text = "This page has enough embedded text to skip OCR fallback."

	# when / then
	assert is_sparse_text(text) is False


def test_given_ocr_param_true_when_requesting_then_returns_true():
	# when / then
	assert ocr_requested(True) is True


def test_given_ocr_env_set_when_requesting_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_OCR", "1")

	# when / then
	assert ocr_requested(None) is True


def test_given_no_ocr_signal_when_active_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_OCR", raising=False)

	# when / then
	assert is_ocr_active() is False


def test_given_tesseract_on_path_when_selecting_engine_then_uses_tesseract(monkeypatch: pytest.MonkeyPatch):
	# given
	reset_ocr_engine()
	monkeypatch.setenv("SRXY_OCR", "1")

	class FakeEngine:
		def recognize(self, image: object) -> str:
			return "invoice total"

	with (
		patch("srxy.ocr_text.tesseract_available", return_value=True),
		patch("srxy.ocr_text.TesseractEngine", return_value=FakeEngine()),  # type: ignore[arg-type]
	):
		from srxy.ocr_text import get_ocr_engine

		# when
		engine = get_ocr_engine()
		text = engine.recognize(object())  # type: ignore[arg-type]

	# then
	assert text == "invoice total"
	reset_ocr_engine()


def test_given_no_tesseract_when_checking_availability_then_returns_false():
	# given
	with patch("srxy.ocr_text.tesseract_available", return_value=False):
		# when / then
		assert is_ocr_available() is False


def test_given_no_tesseract_when_ensuring_ocr_available_then_raises():
	# given
	with patch("srxy.ocr_text.tesseract_available", return_value=False):
		# when / then
		with pytest.raises(RuntimeError, match="Tesseract OCR is not available"):
			ensure_ocr_available()


def test_given_no_tesseract_when_reading_unavailable_message_then_returns_install_hint():
	# when
	message = ocr_unavailable_message()

	# then
	assert "tesseract binary on PATH" in message
	assert "tesseract-ocr" in message


def test_given_mocked_image_ocr_when_iterating_lines_then_yields_text(tmp_path: Path):
	# given
	image_path = tmp_path / "scan.png"
	Image.new("L", (20, 20), color=255).save(image_path)

	with patch("srxy.ocr_text.ocr_pil_image", return_value="quarterly revenue scan"):
		from srxy.ocr_text import iter_image_ocr_lines

		# when
		lines = list(iter_image_ocr_lines(image_path))

	# then
	assert lines == [(1, "quarterly revenue scan")]


def test_given_cached_image_ocr_when_iterating_twice_then_runs_tesseract_once(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	image_path = tmp_path / "scan.png"
	Image.new("L", (20, 20), color=255).save(image_path)
	from srxy.cache import reset_cache_connection
	from srxy.ocr_text import reset_ocr_engine

	reset_cache_connection()
	reset_ocr_engine()

	with patch("srxy.ocr_text.ocr_pil_image", return_value="cached invoice") as ocr_mock:
		# when
		first = list(iter_image_ocr_lines(image_path))
		second = list(iter_image_ocr_lines(image_path))

	# then
	assert first == [(1, "cached invoice")]
	assert second == [(1, "cached invoice")]
	ocr_mock.assert_called_once()
	reset_cache_connection()


def test_given_no_env_when_reading_ocr_max_file_size_then_returns_default(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_OCR_MAX_FILE_SIZE", raising=False)

	# when / then
	assert ocr_max_file_size() == DEFAULT_OCR_MAX_FILE_SIZE


def test_given_color_image_when_preprocessing_then_keeps_rgb():
	# given
	image = Image.new("RGB", (32, 32), color=(255, 0, 0))

	# when
	processed = preprocess_image(image)

	# then
	assert processed.mode == "RGB"


def test_given_multiple_tesseract_outputs_when_selecting_best_then_prefers_readable_text():
	# given
	engine = TesseractEngine()
	image = Image.new("RGB", (8, 8))
	garbage = "-\n\nA\n\nf\\\n"
	good = "MUSIC COMPOSED BY\nBRIAN TYLER"

	def fake_to_string(img: Image.Image, config: str = "") -> str:
		if "--psm 3" in config:
			return good
		return garbage

	with patch("pytesseract.image_to_string", side_effect=fake_to_string):
		# when
		text = engine.recognize(image)

	# then
	assert text == good


def test_given_multiple_tesseract_outputs_when_recognizing_then_returns_best_candidate():
	# given
	engine = TesseractEngine()
	image = Image.new("RGB", (8, 8))

	def fake_to_string(img: Image.Image, config: str = "") -> str:
		if "--psm 3" in config:
			return "MUSIC COMPOSED BY\nBRIAN TYLER"
		return "-\n\nA\n\nf\\\n"

	with patch("pytesseract.image_to_string", side_effect=fake_to_string):
		# when
		text = engine.recognize(image)

	# then
	assert "BRIAN TYLER" in text


@pytest.mark.ocr
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


def test_given_small_and_large_pdf_images_when_ocring_page_then_skips_small_only():
	# given
	small_image = MagicMock()
	small_image.data = b"x" * 100
	large_image = MagicMock()
	large_image.data = b"x" * 25_000
	page = MagicMock()
	page.images = [small_image, large_image]

	def fake_ocr_bytes(data: bytes) -> str:
		return "classifier layer" if len(data) >= 20_000 else ""

	with patch("srxy.ocr_text._ocr_pdf_image_bytes", side_effect=fake_ocr_bytes):
		# when
		text = ocr_pdf_page_images(page)

	# then
	assert text == "classifier layer"


@pytest.mark.ocr
@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
def test_given_ocr_image_fixture_when_running_tesseract_then_reads_revenue():
	# given
	from tests.helpers import OCR_IMAGE_FIXTURE

	# when
	lines = list(iter_image_ocr_lines(OCR_IMAGE_FIXTURE))

	# then
	assert lines
	assert any("revenue" in line_text.lower() for _, line_text in lines)


@pytest.mark.ocr
@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
def test_given_ocr_pdf_fixture_when_running_tesseract_then_reads_classifier():
	# given
	from pypdf import PdfReader
	from tests.helpers import OCR_PDF_FIXTURE

	page = PdfReader(str(OCR_PDF_FIXTURE)).pages[0]

	# when
	text = ocr_pdf_page_images(page)

	# then
	assert "classifier" in text.lower()
