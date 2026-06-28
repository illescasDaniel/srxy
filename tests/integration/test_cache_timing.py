from __future__ import annotations

import time
from pathlib import Path

import pytest

from srxy.cache import reset_cache_connection, reset_run_file_hashes
from srxy.file_search import magic_file_search
from srxy.matchers.semantic import reset_semantic_model
from srxy.semantic_image import reset_semantic_image_model


pytestmark = [pytest.mark.integration, pytest.mark.semantic]

TEMP_DOCS = Path("/home/daniel/Downloads/temp_docs/docs")


@pytest.fixture(autouse=True)
def reset_models():
	reset_semantic_model()
	reset_semantic_image_model()
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_semantic_model()
	reset_semantic_image_model()


@pytest.mark.skipif(not TEMP_DOCS.is_dir(), reason="local temp_docs corpus not available")
def test_given_semantic_all_search_when_running_twice_then_second_run_is_faster(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC", "1")
	monkeypatch.setenv("SRXY_SEMANTIC_IMAGE", "1")
	monkeypatch.setenv("SRXY_OCR", "1")
	monkeypatch.setenv("SRXY_TRANSCRIBE", "1")

	def run_search() -> float:
		started = time.perf_counter()
		magic_file_search(
			TEMP_DOCS,
			"linkin",
			ocr=True,
			transcribe=True,
			semantic_image=True,
			threshold=0.35,
			limit=5,
		)
		return time.perf_counter() - started

	# when
	first = run_search()
	second = run_search()

	# then
	assert second < first * 0.75
