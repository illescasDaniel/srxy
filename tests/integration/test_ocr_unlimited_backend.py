"""Real baidu/Unlimited-OCR backend tests.

Gated on both `[semantic]` extras (torch + transformers importable) *and* a
locally cached model — this repo's CI/dev VMs are not expected to have a GPU
or the 3B-parameter model downloaded, so these tests skip gracefully rather
than triggering a multi-GB download. Real hardware QA (GPU correctness,
speed) is Daniel's follow-up once the draft PR lands.

To exercise this file locally on a machine with `[semantic]` installed:

    uv sync --extra semantic
    python -m srxy.adapters.outbound.models.model_store unlimited-ocr
    uv run pytest tests/integration/test_ocr_unlimited_backend.py -v
"""

from __future__ import annotations

import pytest
from tests.helpers import OCR_FIXTURES_DIR, OCR_IMAGE_FIXTURE, require_file_search_fixtures

from srxy.adapters.outbound.models.model_store import is_model_installed, unlimited_ocr_model_dir
from srxy.adapters.outbound.ocr.ocr_text import (
	UnlimitedOcrEngine,
	get_ocr_engine,
	ocr_pil_image,
	reset_ocr_engine,
	unlimited_ocr_deps_installed,
)


pytestmark = [pytest.mark.integration, pytest.mark.ocr, pytest.mark.semantic]

_unlimited_ocr_ready = unlimited_ocr_deps_installed() and is_model_installed(unlimited_ocr_model_dir())

_requires_unlimited_ocr = pytest.mark.skipif(
	not _unlimited_ocr_ready,
	reason=(
		"Unlimited OCR requires 'srxy[semantic]' (torch + transformers) and a cached "
		"baidu/Unlimited-OCR model — run "
		"`python -m srxy.adapters.outbound.models.model_store unlimited-ocr` first. "
		"Real GPU accuracy/perf QA is tracked separately (see memory/activeContext.md)."
	),
)


@pytest.fixture(autouse=True)
def _reset_engine():
	reset_ocr_engine()
	yield
	reset_ocr_engine()


@_requires_unlimited_ocr
def test_given_semantic_extras_and_model_when_selecting_engine_then_uses_unlimited_ocr():
	# when
	engine = get_ocr_engine()

	# then
	assert isinstance(engine, UnlimitedOcrEngine)


@_requires_unlimited_ocr
def test_given_ocr_image_fixture_when_running_unlimited_ocr_then_reads_revenue():
	# given
	require_file_search_fixtures()
	from PIL import Image

	# when
	with Image.open(OCR_IMAGE_FIXTURE) as image:
		text = ocr_pil_image(image)

	# then
	assert "revenue" in text.lower()


@_requires_unlimited_ocr
def test_given_ocr_fixtures_dir_when_searching_with_ocr_then_finds_revenue():
	# given
	from srxy import magic_file_search

	# when
	results = magic_file_search(
		OCR_FIXTURES_DIR,
		"revenue",
		ocr=True,
		search_names=False,
		semantic_image=False,
		include_subdirectories=False,
	)

	# then
	assert len(results) == 1
	assert results[0].path == OCR_IMAGE_FIXTURE
