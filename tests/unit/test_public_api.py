from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import srxy


pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
EXPORT_SCRIPT = ROOT / "scripts" / "docs" / "export_public_api.py"
API_REFERENCE = ROOT / "docs" / "api-reference.md"

EXPECTED_PUBLIC_API = frozenset(
	{
		"ActivityUpdate",
		"FieldConfig",
		"FileQ",
		"FileSearchResult",
		"LineMatch",
		"MatchType",
		"Q",
		"SearchResult",
		"SkippedFile",
		"magic_file_search",
		"magic_search",
		"search",
	}
)


def _load_export_module():
	spec = importlib.util.spec_from_file_location("export_public_api", EXPORT_SCRIPT)
	assert spec is not None
	assert spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_given_package_init_when_reading_all_then_matches_frozen_public_api():
	# given / when
	exported = set(srxy.__all__)

	# then
	assert exported == EXPECTED_PUBLIC_API
	for name in EXPECTED_PUBLIC_API:
		assert hasattr(srxy, name)


def test_given_public_api_when_rendering_reference_then_matches_committed_docs():
	# given
	export = _load_export_module()

	# when
	rendered = export.render_public_api_markdown()

	# then
	assert API_REFERENCE.is_file(), "docs/api-reference.md missing; run scripts/docs/export_public_api.py"
	assert rendered == API_REFERENCE.read_text(encoding="utf-8")
