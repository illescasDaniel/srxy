from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tests.isolation import apply_isolated_cache_environment

from srxy.application.matching.registry import get_atomic_matcher


@pytest.fixture(autouse=True)
def isolated_unit_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	yield from apply_isolated_cache_environment(tmp_path, monkeypatch)


@pytest.fixture
def mock_semantic_model(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_SEMANTIC", "1")

	def always_installed():
		return True

	monkeypatch.setattr("srxy.application.matching.semantic.sentence_transformers_installed", always_installed)
	monkeypatch.setattr(
		"srxy.adapters.outbound.semantic.semantic_image.sentence_transformers_installed", always_installed
	)
	get_atomic_matcher.cache_clear()
	mock_model = MagicMock()

	def fake_encode(texts: str | list[str]):
		if isinstance(texts, str):
			return [float(hash(texts) % 1000), 0.1]
		return [[float(hash(text) % 1000), 0.1] for text in texts]

	mock_model.encode.side_effect = fake_encode
	monkeypatch.setattr("srxy.application.matching.semantic._get_model", lambda: mock_model)
	monkeypatch.setattr(
		"srxy.application.matching.semantic._cosine_similarity",
		lambda left, right: 1.0 if left[0] == right[0] else 0.75,
	)
	yield
	get_atomic_matcher.cache_clear()
