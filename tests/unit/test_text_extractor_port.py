from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from srxy.adapters.outbound.content.text_extractor import DefaultTextExtractor
from srxy.application.use_cases.search_files import magic_file_search, set_text_extractor
from srxy.domain.models import SkippedFile
from srxy.domain.progress import ActivityCallback
from srxy.domain.text_unit import TextUnit


pytestmark = pytest.mark.unit


class _FakeExtractor(DefaultTextExtractor):
	def __init__(self, units: list[TextUnit]):
		self.units = units
		self.calls = 0

	def iter_units(
		self,
		path: Path,
		max_file_size: int | None,
		*,
		search_docs_tags: bool = True,
		ocr: bool | None = None,
		transcribe: bool | None = None,
		skipped_files: list[SkippedFile] | None = None,
		on_activity: ActivityCallback | None = None,
	) -> Iterator[TextUnit]:
		self.calls += 1
		_ = (path, max_file_size, search_docs_tags, ocr, transcribe, skipped_files, on_activity)
		yield from self.units


def test_given_fake_text_extractor_when_searching_then_matches_injected_units(tmp_path: Path):
	path = tmp_path / "note.txt"
	path.write_text("ignored body", encoding="utf-8")
	fake = _FakeExtractor([TextUnit(line_number=3, text="axolotl habitat", location_kind="line")])
	set_text_extractor(fake)
	try:
		results = magic_file_search(tmp_path, "axolotl", search_names=False, search_contents=True, threshold=0.3)
	finally:
		set_text_extractor(None)

	assert fake.calls >= 1
	assert results
	assert results[0].path == path
	assert any(line.line_number == 3 for line in results[0].lines)


def test_given_file_search_use_case_when_searching_with_extractor_then_uses_it(tmp_path: Path):
	from srxy.application.use_cases.search_files import FileSearchUseCase

	path = tmp_path / "note.txt"
	path.write_text("ignored", encoding="utf-8")
	fake = _FakeExtractor([TextUnit(line_number=1, text="penguin colony", location_kind="line")])
	results = FileSearchUseCase(text_extractor=fake).search(
		tmp_path, "penguin", search_names=False, search_contents=True, threshold=0.3
	)
	assert fake.calls >= 1
	assert results
	assert results[0].path == path


def test_given_image_path_when_ocr_candidate_then_true():
	extractor = DefaultTextExtractor()
	assert extractor.ocr_candidate_path(Path("scan.png")) is True
	assert extractor.ocr_candidate_path(Path("notes.txt")) is False


def test_given_audio_path_when_transcribe_candidate_then_true():
	extractor = DefaultTextExtractor()
	assert extractor.transcribe_candidate_path(Path("track.mp3")) is True
	assert extractor.transcribe_candidate_path(Path("notes.txt")) is False
