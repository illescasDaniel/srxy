"""Content-kind routing: Magika escalation for extensionless and misnamed files."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.adapters.outbound.content.content_kind import (
	clear_content_kind_cache,
	resolve_content_route,
	route_after_document_failure,
)
from srxy.adapters.outbound.content.line_sources import iter_searchable_lines
from srxy.application.use_cases.search_files import magic_file_search


pytestmark = [pytest.mark.unit]

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "content_kind"
_BEEP_OGG = _FIXTURES / "beep.ogg"
_CLIP_MP4 = _FIXTURES / "clip.mp4"


@pytest.fixture(autouse=True)
def _clear_kind_cache():
	clear_content_kind_cache()
	yield
	clear_content_kind_cache()


def _text_bytes(needle: str = "axolotl") -> bytes:
	return (f"hello world about {needle} swimming in the lake.\n" * 20).encode()


def test_given_extensionless_ogg_when_resolving_route_then_media_audio(tmp_path: Path):
	path = tmp_path / "95a4c1e7dc57e1d8fb1dec2349d7474968ecce30"
	shutil.copyfile(_BEEP_OGG, path)
	route = resolve_content_route(path)
	assert route.as_media
	assert not route.body_text
	assert route.logical_suffix in {".ogg", ".oga", ".opus"}


def test_given_extensionless_text_when_resolving_route_then_body_text(tmp_path: Path):
	path = tmp_path / "README"
	path.write_bytes(_text_bytes())
	route = resolve_content_route(path)
	assert route.body_text
	assert not route.as_media


def test_given_mp4_bytes_with_txt_suffix_when_resolving_then_media(tmp_path: Path):
	path = tmp_path / "my_video.txt"
	shutil.copyfile(_CLIP_MP4, path)
	route = resolve_content_route(path)
	assert route.as_media
	assert route.logical_suffix == ".mp4"
	assert not route.body_text


def test_given_text_with_mp4_suffix_when_resolving_then_body_text(tmp_path: Path):
	path = tmp_path / "notes.mp4"
	path.write_bytes(_text_bytes("secret"))
	route = resolve_content_route(path)
	assert route.body_text
	assert not route.as_media


def test_given_text_named_mp4_when_searching_contents_then_matches(tmp_path: Path):
	(tmp_path / "notes.mp4").write_bytes(_text_bytes("secret"))
	results = magic_file_search(tmp_path, "secret", search_names=False)
	assert len(results) == 1
	assert results[0].path.name == "notes.mp4"


def test_given_mp4_named_txt_when_transcribe_enabled_then_runs_transcript_path(tmp_path: Path):
	video = tmp_path / "clip.txt"
	shutil.copyfile(_CLIP_MP4, video)

	def fake_transcript(path: Path, **_kwargs):
		assert path == video
		yield 1, "hello from audio"

	with (
		patch(
			"srxy.adapters.outbound.content.line_sources.is_transcribe_active",
			return_value=True,
		),
		patch(
			"srxy.adapters.outbound.content.line_sources.iter_transcript_lines",
			side_effect=fake_transcript,
		),
	):
		units = list(iter_searchable_lines(video, None, transcribe=True))
	kinds = {kind for _, _, kind in units}
	assert "transcript" in kinds
	assert any("hello from audio" in text for _, text, kind in units if kind == "transcript")


def test_given_corrupt_pdf_that_is_text_when_searching_then_magika_reroutes(tmp_path: Path):
	(tmp_path / "broken.pdf").write_bytes(_text_bytes("axolotl"))
	results = magic_file_search(tmp_path, "axolotl", search_names=False)
	assert len(results) == 1
	assert results[0].path.name == "broken.pdf"


def test_given_document_parse_failure_when_magika_says_ogg_then_media_route(tmp_path: Path):
	path = tmp_path / "lied.pdf"
	shutil.copyfile(_BEEP_OGG, path)
	route = route_after_document_failure(path)
	assert route.as_media
	assert route.logical_suffix in {".ogg", ".oga", ".opus"}


def test_given_extensionless_png_when_resolving_then_media_image(tmp_path: Path):
	import struct
	import zlib

	def chunk(tag: bytes, data: bytes) -> bytes:
		return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

	ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
	raw = zlib.compress(b"\x00\xff\x00\x00")
	png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
	path = tmp_path / "deadbeefcafebabe0123456789abcdef"
	path.write_bytes(png)
	route = resolve_content_route(path)
	assert route.as_media
	assert route.logical_suffix == ".png"
