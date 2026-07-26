from __future__ import annotations

import pytest

from srxy.models import FileSearchResult, LineMatch
from srxy.tui.labels import (
	MATCH_SOURCE_LABELS,
	OPTION_LABELS,
	format_tui_match_labels,
	option_hint,
	option_label,
)


pytestmark = pytest.mark.unit


def test_given_option_ids_when_resolving_labels_then_returns_plain_language():
	assert option_label("so-ocr") == "Text in images"
	assert option_hint("so-ocr") == "Read text in photos, scans, and PDF pages"
	assert option_label("so-semantic") == "Similar meaning"


def test_given_all_option_ids_when_resolving_then_each_has_label_and_hint():
	for checkbox_id, (label, hint) in OPTION_LABELS.items():
		assert option_label(checkbox_id) == label
		assert option_hint(checkbox_id) == hint
		assert label
		assert hint


def test_given_result_with_sources_when_formatting_tui_labels_then_maps_known_sources():
	# given
	result = FileSearchResult(
		path=__file__,
		score=0.8,
		breakdown={"content": 0.8, "semantic_image": 0.2},
		lines=[
			LineMatch(line_number=1, text="hello", score=0.8, location_kind="line"),
			LineMatch(line_number=1, text="world", score=0.9, location_kind="ocr"),
		],
	)

	# when
	labels = format_tui_match_labels(result, threshold=0.35, semantic_image_threshold=0.18)

	# then
	assert "content" in labels
	assert MATCH_SOURCE_LABELS["ocr"] in labels
