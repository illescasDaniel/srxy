"""Resolve GUI preview-panel media source URLs for image/audio/video files (Qt-free).

Images are re-encoded to a capped-size PNG ``data:`` URI via the same Pillow
decode path used for OCR / semantic image search (handles HEIC and camera RAW
without relying on Qt's native image plugins). SVG and audio/video files are
referenced directly via a ``file://`` URL — QML plays audio/video through
``QtMultimedia`` and renders SVG natively.

For video, a best-effort first-frame poster (also a PNG ``data:`` URI) is
extracted via ``ffmpeg`` when available on PATH / the install prefix, so the
preview pane can show a thumbnail before playback starts.
"""

from __future__ import annotations

import base64
import io
import shutil
import subprocess
from pathlib import Path

from srxy.adapters.outbound.content.content_kind import classify_preview_media_kind
from srxy.adapters.outbound.documents.image_formats import open_image_for_vision
from srxy.application.install_paths import resolve_ffmpeg_binary


__all__ = [
	"IMAGE_PREVIEW_MAX_DIMENSION",
	"VIDEO_POSTER_TIMEOUT_SECONDS",
	"resolve_media_preview",
]

IMAGE_PREVIEW_MAX_DIMENSION = 2048
VIDEO_POSTER_TIMEOUT_SECONDS = 10

_NON_PNG_MODES = frozenset({"CMYK", "YCbCr", "LAB", "HSV"})


def resolve_media_preview(path: Path, logical_suffix: str) -> tuple[str, str, str]:
	"""Return ``(preview_kind, media_url, poster_url)`` for a media-routed path.

	``preview_kind`` is one of ``"image"``, ``"audio"``, ``"video"``, or ``""``
	when the suffix is not a previewable media kind or decoding failed.
	``media_url`` is a ``data:`` URI (image) or a ``file://`` URL (audio /
	video / svg); it is ``""`` whenever ``preview_kind`` is ``""``.
	``poster_url`` is a first-frame PNG ``data:`` URI for video when ffmpeg can
	extract one; otherwise ``""`` (images/audio always return ``""``).
	"""
	suffix = (logical_suffix or path.suffix).lower()
	kind = classify_preview_media_kind(suffix)
	if kind == "image":
		url = _image_media_url(path, suffix)
		return (kind, url, "") if url else ("", "", "")
	if kind == "audio":
		url = _file_url(path)
		return (kind, url, "") if url else ("", "", "")
	if kind == "video":
		url = _file_url(path)
		if not url:
			return "", "", ""
		return kind, url, _video_poster_url(path)
	return "", "", ""


def _file_url(path: Path) -> str:
	try:
		return path.resolve().as_uri()
	except (OSError, ValueError):
		return ""


def _ffmpeg_binary() -> str | None:
	vendor = resolve_ffmpeg_binary()
	if vendor is not None:
		return str(vendor)
	return shutil.which("ffmpeg")


def _video_poster_url(path: Path) -> str:
	"""Best-effort first-frame PNG data URI via ffmpeg; ``""`` if unavailable."""
	ffmpeg = _ffmpeg_binary()
	if ffmpeg is None:
		return ""
	scale = f"scale='min({IMAGE_PREVIEW_MAX_DIMENSION},iw)':-2"
	try:
		result = subprocess.run(  # noqa: S603
			[
				ffmpeg,
				"-nostdin",
				"-hide_banner",
				"-loglevel",
				"quiet",
				"-y",
				"-ss",
				"0",
				"-i",
				str(path),
				"-frames:v",
				"1",
				"-vf",
				scale,
				"-f",
				"image2pipe",
				"-vcodec",
				"png",
				"-",
			],
			stdout=subprocess.PIPE,
			stderr=subprocess.DEVNULL,
			check=False,
			timeout=VIDEO_POSTER_TIMEOUT_SECONDS,
		)
	except (OSError, subprocess.TimeoutExpired):
		return ""
	if result.returncode != 0 or not result.stdout:
		return ""
	encoded = base64.b64encode(result.stdout).decode("ascii")
	return f"data:image/png;base64,{encoded}"


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
