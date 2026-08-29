from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.outbound.cache.cache import reset_cache_connection, reset_run_file_hashes


@pytest.fixture(autouse=True)
def isolated_cli_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.delenv("SRXY_SEMANTIC", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE", raising=False)
	monkeypatch.delenv("SRXY_OCR", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE_THRESHOLD", raising=False)
	monkeypatch.delenv("SRXY_AUTO_DOWNLOAD", raising=False)
	# Force plain CLI for these tests even on a graphical session.
	monkeypatch.setenv("CI", "true")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "srxy-cache"))
	monkeypatch.setattr(
		"srxy.adapters.outbound.models.model_store.ensure_semantic_text_model",
		lambda **_kwargs: True,
	)
	monkeypatch.setattr(
		"srxy.adapters.outbound.models.model_store.ensure_semantic_image_model",
		lambda **_kwargs: True,
	)
	monkeypatch.setattr(
		"srxy.adapters.outbound.models.model_store.ensure_transcribe_model",
		lambda **_kwargs: True,
	)
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_cache_connection()
	reset_run_file_hashes()
