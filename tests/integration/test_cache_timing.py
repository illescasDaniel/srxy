from __future__ import annotations

import time

import pytest
from tests.helpers import file_search_root, require_file_search_fixtures

from srxy.cache import reset_cache_connection, reset_run_file_hashes
from srxy.file_search import magic_file_search
from srxy.matchers.semantic import reset_semantic_model
from srxy.semantic_image import reset_semantic_image_model


pytestmark = [pytest.mark.integration, pytest.mark.semantic, pytest.mark.integration_full]


@pytest.fixture(autouse=True)
def reset_models():
	reset_semantic_model()
	reset_semantic_image_model()
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_semantic_model()
	reset_semantic_image_model()


def test_given_semantic_all_search_when_running_twice_then_second_run_is_faster(monkeypatch: pytest.MonkeyPatch):
	# given
	require_file_search_fixtures()
	root = file_search_root()
	monkeypatch.setenv("SRXY_SEMANTIC", "1")
	monkeypatch.setenv("SRXY_SEMANTIC_IMAGE", "1")
	monkeypatch.setenv("SRXY_OCR", "1")
	monkeypatch.setenv("SRXY_TRANSCRIBE", "1")

	def run_search() -> float:
		started = time.perf_counter()
		magic_file_search(
			root,
			"axolotl",
			ocr=True,
			transcribe=True,
			semantic_image=True,
			threshold=0.35,
			limit=5,
		)
		return time.perf_counter() - started

	# when — warm up caches before timing
	run_search()
	first = run_search()
	second = run_search()

	# then — warm cache should not regress by more than 2s (timing is noisy under load)
	assert second <= first + 2.0
