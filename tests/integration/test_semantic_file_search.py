from __future__ import annotations

from pathlib import Path

import pytest

from srxy.file_search import magic_file_search


pytestmark = [pytest.mark.integration, pytest.mark.semantic]


@pytest.fixture
def semantic_things_txt(file_search_root: Path) -> Path:
	path = file_search_root / "semantic" / "things.txt"
	assert path.is_file(), f"missing semantic fixture: {path}"
	return path


def test_given_things_txt_when_searching_new_then_finds_recents(semantic_things_txt: Path):
	# when
	results = magic_file_search(
		semantic_things_txt,
		"new",
		search_names=False,
		search_contents=True,
	)

	# then
	assert len(results) == 1
	assert results[0].path == semantic_things_txt
	assert results[0].score >= 0.35
	assert results[0].lines
	assert results[0].lines[0].location_kind == "line"
	assert "recent" in results[0].lines[0].text.lower()


def test_given_things_txt_when_searching_unrelated_term_then_finds_nothing(semantic_things_txt: Path):
	# when
	results = magic_file_search(
		semantic_things_txt,
		"zzzznonword",
		search_names=False,
		search_contents=True,
	)

	# then
	assert results == []


def test_given_notes_txt_when_searching_salamander_with_semantic_then_finds_axolotl(file_search_root: Path):
	# given
	notes = file_search_root / "notes.txt"

	# when
	results = magic_file_search(
		notes,
		"salamander",
		search_names=False,
		search_contents=True,
	)

	# then
	assert results
	assert results[0].path == notes
	assert results[0].score >= 0.35
	assert any("axolotl" in line.text.lower() for line in results[0].lines)
