from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.cache import reset_cache_connection, reset_run_file_hashes
from srxy.matchers.registry import get_atomic_matcher


@pytest.fixture(autouse=True)
def isolated_unit_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.delenv("SRXY_SEMANTIC", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE", raising=False)
	monkeypatch.delenv("SRXY_OCR", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE_THRESHOLD", raising=False)
	monkeypatch.delenv("SRXY_AUTO_DOWNLOAD", raising=False)
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "srxy-cache"))
	monkeypatch.setattr("srxy.cli.ensure_semantic_text_model", lambda **_kwargs: True)
	monkeypatch.setattr("srxy.cli.ensure_semantic_image_model", lambda **_kwargs: True)
	monkeypatch.setattr("srxy.cli.ensure_transcribe_model", lambda **_kwargs: True)
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_cache_connection()
	reset_run_file_hashes()


@pytest.fixture
def mock_semantic_model(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_SEMANTIC", "1")

	def always_installed():
		return True

	monkeypatch.setattr("srxy.matchers.semantic.sentence_transformers_installed", always_installed)
	monkeypatch.setattr("srxy.cli.sentence_transformers_installed", always_installed)
	monkeypatch.setattr("srxy.semantic_image.sentence_transformers_installed", always_installed)
	get_atomic_matcher.cache_clear()
	mock_model = MagicMock()

	def fake_encode(texts: str | list[str]):
		if isinstance(texts, str):
			return [float(hash(texts) % 1000), 0.1]
		return [[float(hash(text) % 1000), 0.1] for text in texts]

	mock_model.encode.side_effect = fake_encode
	monkeypatch.setattr("srxy.matchers.semantic._get_model", lambda: mock_model)
	monkeypatch.setattr(
		"srxy.matchers.semantic._cosine_similarity",
		lambda left, right: 1.0 if left[0] == right[0] else 0.75,
	)
	yield
	get_atomic_matcher.cache_clear()
