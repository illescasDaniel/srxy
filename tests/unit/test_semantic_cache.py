from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.cache import (
	CACHE_KIND_DOCUMENT_TEXT,
	CACHE_KIND_SEMANTIC_EMBED,
	cache_get,
	hash_bytes,
	reset_cache_connection,
)
from srxy.document_text import iter_document_lines
from srxy.matchers.semantic import SemanticMatcher, reset_semantic_model


pytestmark = [pytest.mark.unit, pytest.mark.semantic, pytest.mark.usefixtures("mock_semantic_model")]


def setup_function():
	reset_semantic_model()
	reset_cache_connection()


def teardown_function():
	reset_semantic_model()
	reset_cache_connection()


@patch("srxy.matchers.semantic._get_model")
def test_given_cached_embedding_when_scoring_twice_then_encodes_once(mock_get_model: MagicMock):
	# given
	np = pytest.importorskip("numpy")
	mock_model = MagicMock()
	mock_model.encode.side_effect = lambda text: np.array([float(len(text)), 0.5], dtype=np.float32)
	mock_get_model.return_value = mock_model
	matcher = SemanticMatcher()
	query = "linkin park"
	value = "in the end"

	# when
	first = matcher.score(query, value)
	second = matcher.score(query, value)

	# then
	assert first == second
	assert mock_model.encode.call_count == 2


@patch("srxy.matchers.semantic._get_model")
def test_given_cached_embedding_when_new_process_scores_again_then_skips_encode(
	mock_get_model: MagicMock,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	np = pytest.importorskip("numpy")
	monkeypatch.setenv("SRXY_SEMANTIC_MODEL", "test-model")
	mock_model = MagicMock()
	mock_model.encode.side_effect = lambda text: np.array([float(len(text)), 0.5], dtype=np.float32)
	mock_get_model.return_value = mock_model
	matcher = SemanticMatcher()
	query = "query"
	text = "cached phrase"

	# when
	matcher.score(query, text)
	reset_semantic_model()
	mock_get_model.return_value = mock_model
	matcher.score(query, text)

	# then
	assert mock_model.encode.call_count == 2
	assert cache_get(CACHE_KIND_SEMANTIC_EMBED, hash_bytes(text.encode("utf-8")), "test-model") is not None


def test_given_pdf_lines_when_iterating_twice_then_extracts_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	from srxy.cache import get_file_content_hash

	pdf_path = tmp_path / "sample.pdf"
	pdf_path.write_bytes(b"%PDF-1.4 cached")
	lines = [(1, "page text", "page"), (2, "ocr text", "ocr")]

	def fake_pdf_lines(path: Path, *, ocr: bool | None = None):
		assert path == pdf_path
		yield from lines

	monkeypatch.setattr("srxy.document_text._iter_pdf_lines", fake_pdf_lines)
	monkeypatch.setattr("srxy.ocr_text.is_ocr_active", lambda _ocr=None: True)

	# when
	first = list(iter_document_lines(pdf_path, ocr=True))
	second = list(iter_document_lines(pdf_path, ocr=True))

	# then
	assert first == lines
	assert second == lines
	content_hash = get_file_content_hash(pdf_path)
	assert cache_get(CACHE_KIND_DOCUMENT_TEXT, content_hash, ".pdf:ocr=1") is not None


@pytest.mark.transcribe
def test_given_empty_transcript_cache_when_iterating_then_skips_transcription(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.cache import CACHE_KIND_TRANSCRIPT, cache_put
	from srxy.transcribe_text import iter_transcript_lines, reset_transcribe_models

	audio = tmp_path / "silent.mp3"
	audio.write_bytes(b"silent-audio")
	content_hash = hash_bytes(b"silent-audio")
	variant = "base-cuda-faster-whisper"
	cache_put(CACHE_KIND_TRANSCRIPT, content_hash, variant, b"")
	reset_transcribe_models()

	def boom(_path: Path):
		raise AssertionError("should not transcribe on empty cache hit")
		yield from []

	with (
		patch("srxy.cache.get_file_content_hash", return_value=content_hash),
		patch("srxy.transcribe_text.resolve_transcribe_device", return_value="cuda"),
		patch("srxy.transcribe_text.transcribe_backend_for_device", return_value="faster-whisper"),
		patch("srxy.transcribe_text._with_normalized_audio", side_effect=boom),
	):
		# when
		result = list(iter_transcript_lines(audio))

	# then
	assert result == []
