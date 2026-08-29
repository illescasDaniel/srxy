"""Shared per-test isolation for non-integration buckets.

Do not import this into ``tests/conftest.py`` — it deletes ``SRXY_SEMANTIC``,
which ``tests/integration/conftest.py`` requires for real-model warmup.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.outbound.cache.cache import reset_cache_connection, reset_run_file_hashes


def apply_isolated_cache_environment(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	*,
	force_ci: bool = False,
):
	"""Scrub heavy-feature env vars, pin a per-test cache dir, stub model ensures."""
	monkeypatch.delenv("SRXY_SEMANTIC", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE", raising=False)
	monkeypatch.delenv("SRXY_OCR", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE_THRESHOLD", raising=False)
	monkeypatch.delenv("SRXY_AUTO_DOWNLOAD", raising=False)
	if force_ci:
		monkeypatch.setenv("CI", "true")
	else:
		monkeypatch.delenv("CI", raising=False)
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "srxy-cache"))
	monkeypatch.setattr("srxy.adapters.inbound.cli.cli.ensure_semantic_text_model", lambda **_kwargs: True)
	monkeypatch.setattr("srxy.adapters.inbound.cli.cli.ensure_semantic_image_model", lambda **_kwargs: True)
	monkeypatch.setattr("srxy.adapters.inbound.cli.cli.ensure_transcribe_model", lambda **_kwargs: True)
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_cache_connection()
	reset_run_file_hashes()
