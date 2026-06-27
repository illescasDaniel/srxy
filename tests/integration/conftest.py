from __future__ import annotations

import os

import pytest
from tests.helpers import LabeledQuery, load_labeled_queries, load_search_corpus

from srxy.matchers.registry import get_atomic_matcher
from srxy.matchers.semantic import is_semantic_available, warmup_semantic_model
from srxy.model_store import ensure_semantic_text_model


pytestmark = pytest.mark.integration


@pytest.fixture(scope="session", autouse=True)
def semantic_search_enabled():  # pyright: ignore[reportUnusedFunction]
	os.environ["SRXY_SEMANTIC"] = "1"
	os.environ.setdefault("SRXY_AUTO_DOWNLOAD", "1")
	get_atomic_matcher.cache_clear()
	yield
	get_atomic_matcher.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def semantic_model_ready(semantic_search_enabled: None):  # pyright: ignore[reportUnusedParameter]
	if not is_semantic_available():
		pytest.skip("Integration tests require SRXY_SEMANTIC=1 and pip install 'srxy[semantic]'")
	if not ensure_semantic_text_model(interactive=False, auto_download=True):
		pytest.skip("Integration tests require the semantic text model (download failed or unavailable)")
	warmup_semantic_model()


@pytest.fixture(scope="module")
def search_corpus() -> list[dict[str, str]]:
	return load_search_corpus()


@pytest.fixture(scope="module")
def labeled_queries() -> list[LabeledQuery]:
	return load_labeled_queries()
