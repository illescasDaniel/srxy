"""Content-kind detection: NUL sniff + Magika escalation for misnamed / extensionless files."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from srxy.adapters.outbound.documents.document_text import DOCUMENT_SUFFIXES
from srxy.adapters.outbound.documents.image_formats import DECODABLE_IMAGE_SUFFIXES
from srxy.adapters.outbound.metadata.media_metadata import (
	AUDIO_SUFFIXES,
	MEDIA_SUFFIXES,
	VIDEO_SUFFIXES,
)


_TEXT_SAMPLE_SIZE = 8192

# Magika labels → logical suffixes used by existing extractors.
_LABEL_TO_SUFFIX: dict[str, str] = {
	"ogg": ".ogg",
	"oga": ".oga",
	"opus": ".opus",
	"mp3": ".mp3",
	"flac": ".flac",
	"m4a": ".m4a",
	"aac": ".aac",
	"wav": ".wav",
	"mp4": ".mp4",
	"m4v": ".m4v",
	"mov": ".mov",
	"webm": ".webm",
	"mkv": ".mkv",
	"avi": ".avi",
	"png": ".png",
	"jpg": ".jpg",
	"jpeg": ".jpeg",
	"gif": ".gif",
	"webp": ".webp",
	"bmp": ".bmp",
	"tif": ".tif",
	"tiff": ".tiff",
	"heic": ".heic",
	"heif": ".heif",
	"pdf": ".pdf",
	"docx": ".docx",
	"doc": ".doc",
	"xlsx": ".xlsx",
	"xls": ".xls",
	"pptx": ".pptx",
	"ppt": ".ppt",
	"txt": ".txt",
	"json": ".json",
	"jsonl": ".json",
	"xml": ".xml",
	"html": ".html",
	"htm": ".html",
	"md": ".md",
	"markdown": ".md",
	"csv": ".csv",
	"yaml": ".yaml",
	"yml": ".yaml",
	"toml": ".toml",
	"py": ".py",
	"js": ".js",
	"ts": ".ts",
	"css": ".css",
	"rs": ".rs",
	"go": ".go",
	"java": ".java",
	"c": ".c",
	"cpp": ".cpp",
	"h": ".h",
	"sh": ".sh",
	"sql": ".sql",
	"rtf": ".rtf",
	"svg": ".svg",
}

_MIME_TO_SUFFIX: dict[str, str] = {
	"audio/ogg": ".ogg",
	"audio/mpeg": ".mp3",
	"audio/flac": ".flac",
	"audio/mp4": ".m4a",
	"audio/aac": ".aac",
	"audio/wav": ".wav",
	"audio/x-wav": ".wav",
	"video/mp4": ".mp4",
	"video/quicktime": ".mov",
	"video/webm": ".webm",
	"video/x-matroska": ".mkv",
	"image/png": ".png",
	"image/jpeg": ".jpg",
	"image/gif": ".gif",
	"image/webp": ".webp",
	"image/bmp": ".bmp",
	"image/tiff": ".tiff",
	"image/heic": ".heic",
	"image/heif": ".heif",
	"application/pdf": ".pdf",
	"application/json": ".json",
	"text/plain": ".txt",
	"text/html": ".html",
	"text/markdown": ".md",
	"text/csv": ".csv",
	"text/xml": ".xml",
	"application/xml": ".xml",
}


@dataclass(frozen=True, slots=True)
class ContentKind:
	"""Resolved content type for routing extractors."""

	label: str
	logical_suffix: str
	is_text: bool
	mime_type: str = ""


@dataclass(frozen=True, slots=True)
class ContentRoute:
	"""How ``iter_searchable_lines`` should treat a path."""

	logical_suffix: str
	body_text: bool
	as_media: bool
	as_document: bool


def read_sample(path: Path, max_bytes: int = _TEXT_SAMPLE_SIZE) -> bytes | None:
	try:
		size = path.stat().st_size
	except OSError:
		return None
	try:
		with path.open("rb") as handle:
			return handle.read(min(max_bytes, size))
	except OSError:
		return None


def sample_has_nul(sample: bytes | None) -> bool:
	return sample is not None and b"\x00" in sample


def path_has_nul(path: Path, max_bytes: int = _TEXT_SAMPLE_SIZE) -> bool:
	return sample_has_nul(read_sample(path, max_bytes))


def _magika() -> object:
	from magika import Magika

	return _magika_singleton(Magika)


@lru_cache(maxsize=1)
def _magika_singleton(factory: type) -> object:
	return factory()


def _cache_key(path: Path) -> tuple[str, int, int] | None:
	try:
		stat = path.stat()
	except OSError:
		return None
	return (str(path.resolve()), int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))), int(stat.st_size))


_kind_cache: dict[tuple[str, int, int], ContentKind | None] = {}


def clear_content_kind_cache() -> None:
	_kind_cache.clear()


def identify_content_kind(path: Path) -> ContentKind | None:
	"""Run Magika on ``path`` (cached by path/mtime/size)."""
	key = _cache_key(path)
	if key is not None and key in _kind_cache:
		return _kind_cache[key]
	kind: ContentKind | None = None
	try:
		result = _magika().identify_path(path)  # type: ignore[attr-defined]
	except Exception:  # noqa: BLE001 — never break search on classifier failure
		kind = None
	else:
		if getattr(result, "ok", False):
			output = result.output
			label = str(getattr(output, "label", "") or "")
			mime = str(getattr(output, "mime_type", "") or "")
			is_text = bool(getattr(output, "is_text", False))
			suffix = _suffix_from_magika(label, mime, getattr(output, "extensions", None))
			kind = ContentKind(label=label, logical_suffix=suffix, is_text=is_text, mime_type=mime)
	if key is not None:
		_kind_cache[key] = kind
	return kind


def _suffix_from_magika(label: str, mime: str, extensions: object) -> str:
	if label in _LABEL_TO_SUFFIX:
		return _LABEL_TO_SUFFIX[label]
	if mime in _MIME_TO_SUFFIX:
		return _MIME_TO_SUFFIX[mime]
	if isinstance(extensions, (list, tuple)) and extensions:
		ext = str(extensions[0]).lower()
		if not ext.startswith("."):
			ext = f".{ext}"
		return ext
	return ""


def is_known_media_suffix(suffix: str) -> bool:
	return suffix in MEDIA_SUFFIXES


def is_known_document_suffix(suffix: str) -> bool:
	return suffix in DOCUMENT_SUFFIXES


def is_media_logical_suffix(suffix: str) -> bool:
	return suffix in MEDIA_SUFFIXES or suffix in {".wav", ".webm", ".mkv", ".avi", ".gif", ".bmp", ".svg"}


def is_document_logical_suffix(suffix: str) -> bool:
	return suffix in DOCUMENT_SUFFIXES or suffix in {".doc", ".xls", ".ppt", ".rtf"}


def is_transcribe_logical_suffix(suffix: str) -> bool:
	return suffix in AUDIO_SUFFIXES or suffix in VIDEO_SUFFIXES or suffix in {".wav", ".webm", ".mkv", ".avi"}


def is_ocr_image_logical_suffix(suffix: str) -> bool:
	return suffix in DECODABLE_IMAGE_SUFFIXES


def resolve_content_route(path: Path) -> ContentRoute:
	"""Decide body-text / media / document routing for a filesystem path.

	Trusts known media/doc suffixes when content matches; escalates to Magika on
	extensionless paths, NUL mismatches for text-oriented names, and media-that-is-text.
	Document parse failures use :func:`route_after_document_failure`.
	"""
	suffix = path.suffix.lower()
	has_nul = path_has_nul(path)

	if is_known_media_suffix(suffix):
		if not has_nul:
			kind = identify_content_kind(path)
			if kind is not None and kind.is_text:
				return ContentRoute(
					logical_suffix=kind.logical_suffix or ".txt",
					body_text=True,
					as_media=False,
					as_document=False,
				)
		return ContentRoute(logical_suffix=suffix, body_text=False, as_media=True, as_document=False)

	if is_known_document_suffix(suffix):
		return ContentRoute(logical_suffix=suffix, body_text=False, as_media=False, as_document=True)

	# Extensionless: always Magika (text or binary typing).
	if not suffix:
		kind = identify_content_kind(path)
		return _route_from_kind(kind, fallback_suffix="", allow_body_text=not has_nul)

	# Named text/unknown suffix: Magika only when NUL says "not plain text".
	if has_nul:
		kind = identify_content_kind(path)
		# NULs contradict Magika is_text — never UTF-8-search these bytes.
		return _route_from_kind(kind, fallback_suffix=suffix, allow_body_text=False)

	return ContentRoute(logical_suffix=suffix, body_text=True, as_media=False, as_document=False)


def route_after_document_failure(path: Path) -> ContentRoute:
	"""Re-route after a document extractor raises / cannot parse."""
	kind = identify_content_kind(path)
	has_nul = path_has_nul(path)
	return _route_from_kind(kind, fallback_suffix="", allow_body_text=not has_nul)


def _route_from_kind(
	kind: ContentKind | None,
	*,
	fallback_suffix: str,
	allow_body_text: bool,
) -> ContentRoute:
	if kind is None:
		if allow_body_text:
			return ContentRoute(
				logical_suffix=fallback_suffix or ".txt",
				body_text=True,
				as_media=False,
				as_document=False,
			)
		return ContentRoute(logical_suffix=fallback_suffix, body_text=False, as_media=False, as_document=False)

	suffix = kind.logical_suffix or fallback_suffix
	if is_document_logical_suffix(suffix):
		return ContentRoute(logical_suffix=suffix, body_text=False, as_media=False, as_document=True)
	if is_media_logical_suffix(suffix):
		return ContentRoute(logical_suffix=suffix, body_text=False, as_media=True, as_document=False)
	if allow_body_text and kind.is_text:
		return ContentRoute(logical_suffix=suffix or ".txt", body_text=True, as_media=False, as_document=False)
	return ContentRoute(logical_suffix=suffix, body_text=False, as_media=False, as_document=False)
