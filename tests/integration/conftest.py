from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.helpers import LabeledQuery, load_labeled_queries, load_search_corpus, require_file_search_fixtures

from srxy.matchers.registry import get_atomic_matcher
from srxy.matchers.semantic import is_semantic_available, warmup_semantic_model
from srxy.model_store import ensure_semantic_image_model, ensure_semantic_text_model
from srxy.semantic_image import is_semantic_image_available, warmup_semantic_image_model


pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def file_search_root() -> Path:
	if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}:
		pytest.skip("File-search fixture tests are disabled in CI")
	return require_file_search_fixtures()


@pytest.fixture(scope="session")
def file_search_samples(file_search_root: Path) -> Path:
	return file_search_root / "samples"


@pytest.fixture(scope="session", autouse=True)
def file_search_semantic_image_env():
	if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}:
		yield
		return
	previous = os.environ.get("SRXY_SEMANTIC_IMAGE")
	os.environ["SRXY_SEMANTIC_IMAGE"] = "1"
	yield
	if previous is None:
		os.environ.pop("SRXY_SEMANTIC_IMAGE", None)
	else:
		os.environ["SRXY_SEMANTIC_IMAGE"] = previous


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
	if os.environ.get("SRXY_SEMANTIC_IMAGE", "").strip().lower() in {"1", "true", "yes", "on"}:
		if is_semantic_image_available() and ensure_semantic_image_model(interactive=False, auto_download=True):
			warmup_semantic_image_model()


@pytest.fixture(scope="module")
def search_corpus() -> list[dict[str, str]]:
	return load_search_corpus()


@pytest.fixture(scope="module")
def labeled_queries() -> list[LabeledQuery]:
	return load_labeled_queries()
