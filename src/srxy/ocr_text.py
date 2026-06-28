from __future__ import annotations

import importlib.util
import io
import os
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
	from PIL import Image

from srxy.image_formats import DECODABLE_IMAGE_SUFFIXES, open_image


_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})
DEFAULT_MAX_IMAGE_DIMENSION = 4000
MIN_OCR_QUALITY_SCORE = 80.0
MIN_PDF_IMAGE_OCR_BYTES = 20_000
SPARSE_TEXT_THRESHOLD = 20
OCR_ENGINE_VARIANT = "tesseract-v4"

OCR_IMAGE_SUFFIXES = DECODABLE_IMAGE_SUFFIXES

_OCR_UNAVAILABLE_MESSAGE = (
	"Tesseract OCR is not available. Install the tesseract binary on PATH "
	"(e.g. tesseract-ocr on Debian/Ubuntu, tesseract on Arch)."
)

_ocr_engine: OcrEngine | None = None


class OcrEngine(ABC):
	@abstractmethod
	def recognize(self, image: Image.Image) -> str: ...


class TesseractEngine(OcrEngine):
	def recognize(self, image: Image.Image) -> str:
		import pytesseract

		best_text = ""
		best_rank = (-1.0, 0)
		for priority, psm in enumerate((3, 6, 11, 12)):
			text = str(pytesseract.image_to_string(image, config=f"--psm {psm}")).strip()
			if not text:
				continue
			score = _ocr_quality_score(text)
			if psm == 3 and score >= MIN_OCR_QUALITY_SCORE:
				return text
			rank = (score, -priority)
			if rank > best_rank:
				best_rank = rank
				best_text = text
		default_text = str(pytesseract.image_to_string(image)).strip()
		if default_text:
			rank = (_ocr_quality_score(default_text), -4)
			if rank > best_rank:
				best_text = default_text
		return best_text


def ocr_env_enabled() -> bool:
	value = os.environ.get("SRXY_OCR", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def tesseract_available() -> bool:
	if importlib.util.find_spec("pytesseract") is None:
		return False
	return shutil.which("tesseract") is not None


def is_ocr_available() -> bool:
	return tesseract_available()


def ocr_requested(ocr: bool | None) -> bool:
	if ocr is not None:
		return ocr
	return ocr_env_enabled()


def is_ocr_active(ocr: bool | None = None) -> bool:
	return ocr_requested(ocr) and is_ocr_available()


def ocr_max_file_size() -> int | None:
	raw = os.environ.get("SRXY_OCR_MAX_FILE_SIZE", "").strip()
	if not raw:
		return None
	try:
		return int(raw)
	except ValueError:
		return None


def is_sparse_text(text: str) -> bool:
	return len(text.strip()) < SPARSE_TEXT_THRESHOLD


def is_ocr_image_path(path: Path) -> bool:
	return path.suffix.lower() in OCR_IMAGE_SUFFIXES


def ocr_unavailable_message() -> str:
	return _OCR_UNAVAILABLE_MESSAGE


def ensure_ocr_available():
	if not tesseract_available():
		raise RuntimeError(_OCR_UNAVAILABLE_MESSAGE)


def get_ocr_engine() -> OcrEngine:
	global _ocr_engine
	if _ocr_engine is None:
		ensure_ocr_available()
		_ocr_engine = TesseractEngine()
	return _ocr_engine


def reset_ocr_engine():
	global _ocr_engine
	_ocr_engine = None


def preprocess_image(image: Image.Image) -> Image.Image:
	from PIL import Image as PILImage

	if image.mode not in {"RGB", "L"}:
		image = image.convert("RGB")
	width, height = image.size
	max_dimension = max(width, height)
	if max_dimension > DEFAULT_MAX_IMAGE_DIMENSION:
		scale = DEFAULT_MAX_IMAGE_DIMENSION / max_dimension
		new_size = (int(width * scale), int(height * scale))
		image = image.resize(new_size, PILImage.Resampling.BICUBIC)
	return image


def _ocr_quality_score(text: str) -> float:
	import re

	collapsed = " ".join(text.split())
	long_words = re.findall(r"[a-z]{4,}", collapsed.lower())
	if not long_words:
		return 0.0
	compactness = len(collapsed) / max(len(text), 1)
	short_line_penalty = sum(1 for line in text.splitlines() if 0 < len(line.strip()) <= 2) * 10
	return len(long_words) * 25 * compactness - short_line_penalty


def ocr_pil_image(image: Image.Image) -> str:
	engine = get_ocr_engine()
	processed = preprocess_image(image)
	return engine.recognize(processed)


def _cached_ocr_text(kind: str, content_hash: str, recognize: Callable[[], str]) -> str:
	from srxy.cache import CACHE_KIND_OCR_IMAGE, CACHE_KIND_OCR_PDF_BLOB, cache_get, cache_put

	if kind not in {CACHE_KIND_OCR_IMAGE, CACHE_KIND_OCR_PDF_BLOB}:
		raise ValueError(f"unsupported OCR cache kind: {kind}")

	cached = cache_get(kind, content_hash, OCR_ENGINE_VARIANT)
	if cached is not None:
		return cached.decode("utf-8")

	text = recognize().strip()
	cache_put(kind, content_hash, OCR_ENGINE_VARIANT, text.encode("utf-8"))
	return text


def ocr_pdf_page_images(page: object) -> str:
	images = getattr(page, "images", None)
	if not images:
		return ""

	parts: list[str] = []
	for img in images:
		data = img.data if hasattr(img, "data") else b""
		if len(data) < MIN_PDF_IMAGE_OCR_BYTES:
			continue
		text = _ocr_pdf_image_bytes(data)
		if text:
			parts.append(text)
	return "\n".join(parts)


def _ocr_pdf_image_bytes(data: bytes) -> str:
	from PIL import Image

	from srxy.cache import CACHE_KIND_OCR_PDF_BLOB, hash_bytes

	content_hash = hash_bytes(data)

	def recognize() -> str:
		try:
			with Image.open(io.BytesIO(data)) as image:
				return ocr_pil_image(image)
		except Exception:
			return ""

	return _cached_ocr_text(CACHE_KIND_OCR_PDF_BLOB, content_hash, recognize)


def iter_image_ocr_lines(path: Path) -> Iterator[tuple[int, str]]:
	from srxy.cache import CACHE_KIND_OCR_IMAGE, get_file_content_hash

	try:
		content_hash = get_file_content_hash(path)

		def recognize() -> str:
			with open_image(path) as image:
				return ocr_pil_image(image)

		text = _cached_ocr_text(CACHE_KIND_OCR_IMAGE, content_hash, recognize)
	except Exception:
		return
	text = text.strip()
	if text:
		yield 1, text
