"""Resolve GUI preview-panel media source URLs for image/audio/video files (Qt-free).

Images are re-encoded to a capped-size PNG ``data:`` URI via the same Pillow
decode path used for OCR / semantic image search (handles HEIC and camera RAW
without relying on Qt's native image plugins). SVG and audio/video files are
referenced directly via a ``file://`` URL — QML plays audio/video through
``QtMultimedia`` and renders SVG natively.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from srxy.adapters.outbound.content.content_kind import classify_preview_media_kind
from srxy.adapters.outbound.documents.image_formats import open_image_for_vision


__all__ = [
	"IMAGE_PREVIEW_MAX_DIMENSION",
	"resolve_media_preview",
]

IMAGE_PREVIEW_MAX_DIMENSION = 2048

_NON_PNG_MODES = frozenset({"CMYK", "YCbCr", "LAB", "HSV"})


def resolve_media_preview(path: Path, logical_suffix: str) -> tuple[str, str]:
	"""Return ``(preview_kind, media_url)`` for a media-routed path.

	``preview_kind`` is one of ``"image"``, ``"audio"``, ``"video"``, or ``""``
	when the suffix is not a previewable media kind or decoding failed.
	``media_url`` is a ``data:`` URI (image) or a ``file://`` URL (audio /
	video / svg); it is ``""`` whenever ``preview_kind`` is ``""``.
	"""
	suffix = (logical_suffix or path.suffix).lower()
	kind = classify_preview_media_kind(suffix)
	if kind == "image":
		url = _image_media_url(path, suffix)
		return (kind, url) if url else ("", "")
	if kind in {"audio", "video"}:
		url = _file_url(path)
		return (kind, url) if url else ("", "")
	return "", ""


def _file_url(path: Path) -> str:
	try:
		return path.resolve().as_uri()
	except (OSError, ValueError):
		return ""


def _image_media_url(path: Path, suffix: str) -> str:
	if suffix == ".svg":
		return _file_url(path)
	try:
		with open_image_for_vision(path) as image:
			if image.mode in _NON_PNG_MODES:
				image = image.convert("RGB")
			image.thumbnail((IMAGE_PREVIEW_MAX_DIMENSION, IMAGE_PREVIEW_MAX_DIMENSION))
			buffer = io.BytesIO()
			image.save(buffer, format="PNG")
	except Exception:  # noqa: BLE001 — never break preview on a decode failure
		return ""
	encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
	return f"data:image/png;base64,{encoded}"
