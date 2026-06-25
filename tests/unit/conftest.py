from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from srxy.matchers.registry import get_atomic_matcher


@pytest.fixture(autouse=True)
def mock_semantic_model(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_SEMANTIC", "1")
	get_atomic_matcher.cache_clear()
	mock_model = MagicMock()
	mock_model.encode.side_effect = lambda texts: [[float(hash(text) % 1000), 0.1] for text in texts]
	monkeypatch.setattr("srxy.matchers.semantic._get_model", lambda: mock_model)
	monkeypatch.setattr(
		"srxy.matchers.semantic._cosine_similarity",
		lambda left, right: 1.0 if left[0] == right[0] else 0.75,
	)
	yield
	get_atomic_matcher.cache_clear()
