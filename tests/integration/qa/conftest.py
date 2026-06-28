"""QA integration tests use the committed corpus under tests/fixtures/qa_corpus/."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.helpers import require_qa_corpus


def pytest_collection_finish(session: pytest.Session):
	if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}:
		return
	if os.environ.get("SRXY_QA_BOOTSTRAP", "").strip() not in {"1", "true", "yes", "on"}:
		return
	qa_count = sum(1 for item in session.items if item.get_closest_marker("qa") is not None)
	if qa_count == 0:
		session.config.warn("SRXY", "SRXY_QA_BOOTSTRAP=1 but no qa-marked tests were collected")


@pytest.fixture(autouse=True)
def qa_semantic_image_env(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_SEMANTIC_IMAGE", "1")


@pytest.fixture(scope="session")
def qa_root() -> Path:
	if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}:
		pytest.skip("QA corpus tests are disabled in CI")
	return require_qa_corpus()


@pytest.fixture(scope="session")
def qa_docs(qa_root: Path) -> Path:
	return qa_root / "docs"


@pytest.fixture(scope="session")
def qa_downloads(qa_root: Path) -> Path:
	return qa_root / "qa_downloads"
