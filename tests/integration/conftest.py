from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.helpers import LabeledQuery, load_labeled_queries, load_search_corpus, require_file_search_fixtures

from srxy.adapters.outbound.models.model_store import ensure_semantic_image_model, ensure_semantic_text_model
from srxy.adapters.outbound.semantic.semantic_image import is_semantic_image_available, warmup_semantic_image_model
from srxy.application.matching.registry import get_atomic_matcher
from srxy.application.matching.semantic import is_semantic_available, warmup_semantic_model


pytestmark = pytest.mark.integration


_INTEGRATION_ROOT = Path(__file__).resolve().parent
# Cold sentence-transformers → sklearn → scipy import + model load often exceeds the
# default 60s pytest-timeout when charged to the first integration test (Windows).
_INTEGRATION_TIMEOUT_SECONDS = 300


def pytest_collection_modifyitems(items: list[pytest.Item]):
	mark = pytest.mark.xdist_group("integration")
	long_timeout = pytest.mark.timeout(_INTEGRATION_TIMEOUT_SECONDS)
	for item in items:
		try:
			item.path.resolve().relative_to(_INTEGRATION_ROOT)
		except ValueError:
			continue
		item.add_marker(mark)
		item.add_marker(long_timeout)


def pytest_sessionstart(session: pytest.Session):
	"""Warm semantic models outside any test's pytest-timeout budget.

	Session autouse fixtures still run in the first test's setup phase, so a 60s
	per-test timeout can kill Windows runs while scipy DLLs load. Session start is
	not covered by pytest-timeout's per-test timer.
	"""
	_ = session
	if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}:
		return
	os.environ.setdefault("SRXY_SEMANTIC", "1")
	os.environ.setdefault("SRXY_AUTO_DOWNLOAD", "1")
	# Match file_search_semantic_image_env so image warmup can run here too.
	os.environ.setdefault("SRXY_SEMANTIC_IMAGE", "1")
	if not is_semantic_available():
		return
	if not ensure_semantic_text_model(interactive=False, auto_download=True):
		return
	warmup_semantic_model()
	if is_semantic_image_available() and ensure_semantic_image_model(interactive=False, auto_download=True):
		warmup_semantic_image_model()


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
	"""Require a warm semantic text model; heavy import/load happens in sessionstart."""
	if not is_semantic_available():
		pytest.skip(
			"Integration tests require SRXY_SEMANTIC=1 and "
			"uv tool install 'srxy[semantic]' (or: pipx install 'srxy[semantic]')"
		)
	if not ensure_semantic_text_model(interactive=False, auto_download=True):
		pytest.skip("Integration tests require the semantic text model (download failed or unavailable)")
	# Idempotent if pytest_sessionstart already warmed; otherwise loads here (CI skip path).
	warmup_semantic_model()


@pytest.fixture(scope="module")
def search_corpus() -> list[dict[str, str]]:
	return load_search_corpus()


@pytest.fixture(scope="module")
def labeled_queries() -> list[LabeledQuery]:
	return load_labeled_queries()
