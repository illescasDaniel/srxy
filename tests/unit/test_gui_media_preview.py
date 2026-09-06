"""Unit tests for GUI media preview resolution (image/audio/video)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from srxy.adapters.inbound.gui.media_preview import resolve_media_preview
from srxy.adapters.outbound.content.content_kind import classify_preview_media_kind


pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_JPG = _FIXTURES / "minimal.jpg"
_BEEP_OGG = _FIXTURES / "content_kind" / "beep.ogg"
_CLIP_MP4 = _FIXTURES / "content_kind" / "clip.mp4"


@pytest.mark.parametrize(
	("suffix", "expected"),
	[
		(".jpg", "image"),
		(".jpeg", "image"),
		(".png", "image"),
		(".webp", "image"),
		(".gif", "image"),
		(".bmp", "image"),
		(".svg", "image"),
		(".heic", "image"),
		(".cr2", "image"),
		(".mp3", "audio"),
		(".flac", "audio"),
		(".wav", "audio"),
		(".mp4", "video"),
		(".mov", "video"),
		(".webm", "video"),
		(".mkv", "video"),
		(".avi", "video"),
		(".txt", ""),
		(".pdf", ""),
	],
)
def test_given_suffix_when_classifying_then_returns_expected_kind(suffix: str, expected: str):
	assert classify_preview_media_kind(suffix) == expected


def test_given_jpeg_image_when_resolving_preview_then_returns_data_uri(tmp_path: Path):
	path = tmp_path / "photo.jpg"
	shutil.copyfile(_JPG, path)

	kind, url = resolve_media_preview(path, ".jpg")

	assert kind == "image"
	assert url.startswith("data:image/png;base64,")


def test_given_audio_file_when_resolving_preview_then_returns_file_url(tmp_path: Path):
	path = tmp_path / "beep.ogg"
	shutil.copyfile(_BEEP_OGG, path)

	kind, url = resolve_media_preview(path, ".ogg")

	assert kind == "audio"
	assert url.startswith("file://")
	assert path.name in url


def test_given_video_file_when_resolving_preview_then_returns_file_url(tmp_path: Path):
	path = tmp_path / "clip.mp4"
	shutil.copyfile(_CLIP_MP4, path)

	kind, url = resolve_media_preview(path, ".mp4")

	assert kind == "video"
	assert url.startswith("file://")
	assert path.name in url


def test_given_svg_file_when_resolving_preview_then_returns_file_url_not_data_uri(tmp_path: Path):
	path = tmp_path / "icon.svg"
	path.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")

	kind, url = resolve_media_preview(path, ".svg")

	assert kind == "image"
	assert url.startswith("file://")


def test_given_corrupt_image_bytes_when_resolving_preview_then_falls_back_empty(tmp_path: Path):
	path = tmp_path / "broken.png"
	path.write_bytes(b"not a real png")

	kind, url = resolve_media_preview(path, ".png")

	assert kind == ""
	assert url == ""


def test_given_non_media_suffix_when_resolving_preview_then_empty(tmp_path: Path):
	path = tmp_path / "notes.txt"
	path.write_text("hello", encoding="utf-8")

	kind, url = resolve_media_preview(path, ".txt")

	assert kind == ""
	assert url == ""
