from __future__ import annotations

import importlib.util
import io
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
	from PIL import Image

COMMON_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"})
HEIF_IMAGE_SUFFIXES = frozenset({".heic", ".heif"})
DECODABLE_IMAGE_SUFFIXES = COMMON_IMAGE_SUFFIXES | HEIF_IMAGE_SUFFIXES
RAW_IMAGE_SUFFIXES = frozenset(
	{
		".arw",
		".cr2",
		".cr3",
		".dng",
		".nef",
		".nrw",
		".orf",
		".pef",
		".raf",
		".raw",
		".rw2",
		".srw",
	}
)
SEMANTIC_IMAGE_SUFFIXES = DECODABLE_IMAGE_SUFFIXES | RAW_IMAGE_SUFFIXES

_heif_registered = False


def register_image_openers():
	global _heif_registered
	if _heif_registered:
		return
	try:
		import pillow_heif  # type: ignore[import-untyped]
	except ImportError:
		return
	pillow_heif.register_heif_opener()
	_heif_registered = True


def heif_support_available() -> bool:
	return importlib.util.find_spec("pillow_heif") is not None


def rawpy_available() -> bool:
	return importlib.util.find_spec("rawpy") is not None


def is_decodable_image_path(path: Path) -> bool:
	return path.suffix.lower() in DECODABLE_IMAGE_SUFFIXES


def is_heif_image_path(path: Path) -> bool:
	return path.suffix.lower() in HEIF_IMAGE_SUFFIXES


def is_raw_image_path(path: Path) -> bool:
	return path.suffix.lower() in RAW_IMAGE_SUFFIXES


def is_semantic_image_path(path: Path) -> bool:
	return path.suffix.lower() in SEMANTIC_IMAGE_SUFFIXES


def _extract_raw_thumbnail(raw: object) -> Image.Image | None:
	from PIL import Image

	try:
		thumb = raw.extract_thumb()  # type: ignore[union-attr]
	except Exception:
		return None
	try:
		if isinstance(thumb.data, (bytes, bytearray)):
			return Image.open(io.BytesIO(thumb.data))
		return Image.fromarray(thumb.data)
	except Exception:
		return None


def _open_raw_image(path: Path) -> Image.Image:
	import rawpy  # type: ignore[import-untyped]
	from PIL import Image

	with rawpy.imread(str(path)) as raw:
		thumb_image = _extract_raw_thumbnail(raw)
		if thumb_image is not None:
			return thumb_image
		rgb = raw.postprocess(use_camera_wb=True, half_size=True)
		return Image.fromarray(rgb)


@contextmanager
def open_image(path: Path) -> Generator[Image.Image]:
	from PIL import Image

	register_image_openers()
	with Image.open(path) as image:
		yield image


@contextmanager
def open_image_for_vision(path: Path) -> Generator[Image.Image]:
	if is_raw_image_path(path):
		if not rawpy_available():
			raise OSError(f"RAW image support requires rawpy: {path}")
		image = _open_raw_image(path)
		try:
			yield image
		finally:
			image.close()
		return
	with open_image(path) as image:
		yield image
