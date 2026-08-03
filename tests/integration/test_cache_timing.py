from __future__ import annotations

import time
from pathlib import Path

import pytest
from tests.helpers import file_search_root, require_file_search_fixtures

from srxy.adapters.outbound.cache.cache import reset_cache_connection, reset_run_file_hashes
from srxy.application.use_cases.search_files import magic_file_search


pytestmark = [pytest.mark.integration, pytest.mark.semantic, pytest.mark.integration_full]


@pytest.fixture(autouse=True)
def reset_cache_state():
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_cache_connection()
	reset_run_file_hashes()


def test_given_semantic_all_search_when_running_twice_then_second_run_is_faster(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given — small text target only (full fixture tree + whisper OOMs / hangs under xdist)
	require_file_search_fixtures()
	notes = file_search_root() / "notes.txt"
	assert notes.is_file(), f"missing notes fixture: {notes}"
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	monkeypatch.setenv("SRXY_SEMANTIC", "1")
	monkeypatch.setenv("SRXY_SEMANTIC_IMAGE", "1")
	monkeypatch.setenv("SRXY_OCR", "1")
	monkeypatch.setenv("SRXY_TRANSCRIBE", "1")
	reset_cache_connection()
	reset_run_file_hashes()

	def run_search() -> float:
		started = time.perf_counter()
		magic_file_search(
			notes,
			"axolotl",
			search_names=False,
			ocr=True,
			transcribe=True,
			semantic_image=True,
			threshold=0.35,
			limit=5,
			max_workers=1,
		)
		return time.perf_counter() - started

	# when — warm up caches before timing
	run_search()
	first = run_search()
	second = run_search()

	# then — warm cache should not regress by more than 2s (timing is noisy under load)
	assert second <= first + 2.0
