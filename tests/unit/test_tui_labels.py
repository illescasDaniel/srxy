from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.tui.labels import (
	format_tui_match_labels,
	option_hint,
	option_label,
)
from srxy.domain.models import FileSearchResult, LineMatch
from srxy.i18n import set_language, tr


pytestmark = pytest.mark.unit

_OPTION_IDS = (
	"so-ocr",
	"so-semantic",
	"so-names",
	"so-content",
	"so-docs-tags",
	"so-hidden",
	"so-noise",
	"so-noise-files",
	"so-match-skipped-names",
	"so-archives",
	"so-subdirs",
	"so-enable-all",
	"so-semantic-image",
	"so-transcribe",
)


def test_given_option_ids_when_resolving_labels_then_returns_plain_language():
	set_language("en")
	assert option_label("so-ocr") == tr("gui.options.ocr")
	assert option_hint("so-ocr") == tr("tui.hint.ocr")
	assert option_label("so-semantic") == tr("gui.options.semantic")


def test_given_all_option_ids_when_resolving_then_each_has_label_and_hint():
	set_language("en")
	for checkbox_id in _OPTION_IDS:
		label = option_label(checkbox_id)
		hint = option_hint(checkbox_id)
		assert label
		assert hint


def test_given_result_with_sources_when_formatting_tui_labels_then_maps_known_sources():
	set_language("en")
	result = FileSearchResult(
		path=Path(__file__),
		score=0.8,
		breakdown={"content": 0.8, "semantic_image": 0.2},
		lines=[
			LineMatch(line_number=1, text="hello", score=0.8, location_kind="line"),
			LineMatch(line_number=1, text="world", score=0.9, location_kind="ocr"),
		],
	)
	labels = format_tui_match_labels(result, threshold=0.35, semantic_image_threshold=0.18)
	assert tr("tui.match.content") in labels
	assert tr("tui.match.image_text") in labels
