"""Unit tests for GUI list models."""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.gui.models import MatchesModel
from srxy.domain.models import FileSearchResult, LineMatch


pytestmark = pytest.mark.unit


def test_given_long_match_lines_when_loading_matches_then_tracks_max_text_length():
	# given
	model = MatchesModel()
	short = "x" * 20
	long = "y" * 120
	result = FileSearchResult(
		path=Path("sample.txt"),
		score=1.0,
		lines=[
			LineMatch(line_number=1, text=short, score=1.0),
			LineMatch(line_number=2, text=long, score=1.0),
		],
	)

	# when
	model.load_from_result(result, query="y")

	# then — preview plain text is capped for display grouping
	assert model.maxTextLength == 100
	assert model.maxTextLength > len(short)
