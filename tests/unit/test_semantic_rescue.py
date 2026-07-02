from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.file_search import (
	_score_line,  # pyright: ignore[reportPrivateUsage]
	_semantic_rescue_score,  # pyright: ignore[reportPrivateUsage]
	magic_file_search,
)
from srxy.matchers.composite import CompositeMatcher
from srxy.models import MatchType


pytestmark = pytest.mark.unit


def test_given_semantic_disabled_when_rescuing_then_returns_composite_score():
	# given
	with patch("srxy.matchers.registry.is_matcher_available", return_value=False):
		# when
		rescued = _semantic_rescue_score(0.25, {"semantic": 0.56}, line_threshold=0.35)

	# then
	assert rescued == pytest.approx(0.25)


def test_given_strong_semantic_and_weak_composite_when_rescuing_then_uses_semantic():
	# given
	with patch("srxy.matchers.registry.is_matcher_available", return_value=True):
		# when
		rescued = _semantic_rescue_score(0.25, {"semantic": 0.56, "fuzzy": 0.38}, line_threshold=0.35)

	# then
	assert rescued == pytest.approx(0.56)


def test_given_composite_above_threshold_when_rescuing_then_keeps_composite():
	# given
	with patch("srxy.matchers.registry.is_matcher_available", return_value=True):
		# when
		rescued = _semantic_rescue_score(0.40, {"semantic": 0.56, "fuzzy": 0.40}, line_threshold=0.35)

	# then
	assert rescued == pytest.approx(0.40)


def test_given_semantic_below_gate_when_rescuing_then_keeps_composite():
	# given
	with patch("srxy.matchers.registry.is_matcher_available", return_value=True):
		# when
		rescued = _semantic_rescue_score(0.25, {"semantic": 0.45, "fuzzy": 0.38}, line_threshold=0.35)

	# then
	assert rescued == pytest.approx(0.25)


def test_given_related_query_when_scoring_content_line_then_rescues_semantic_score():
	# given
	matcher = CompositeMatcher()

	with (
		patch.object(matcher, "score_with_breakdown", return_value=(0.245, {"semantic": 0.56, "fuzzy": 0.38})),
		patch("srxy.matchers.registry.is_matcher_available", return_value=True),
	):
		# when
		score = _score_line(matcher, "new", "recents", "line", line_threshold=0.35)

	# then
	assert score == pytest.approx(0.56)


def test_given_unrelated_query_when_scoring_content_line_then_keeps_composite_score():
	# given
	matcher = CompositeMatcher()

	with (
		patch.object(matcher, "score_with_breakdown", return_value=(0.12, {"semantic": 0.18, "fuzzy": 0.12})),
		patch("srxy.matchers.registry.is_matcher_available", return_value=True),
	):
		# when
		score = _score_line(matcher, "zzzz", "recents", "line", line_threshold=0.35)

	# then
	assert score == pytest.approx(0.12)


def test_given_related_query_when_searching_things_txt_then_finds_recents(tmp_path: Path):
	# given
	text_path = tmp_path / "things.txt"
	text_path.write_text("recents\n", encoding="utf-8")

	with (
		patch("srxy.file_search.CompositeMatcher") as composite_matcher,
		patch("srxy.matchers.registry.is_matcher_available", return_value=True),
	):
		composite_matcher.return_value.score_with_breakdown.side_effect = lambda q, value: (
			(0.245, {"semantic": 0.56, "fuzzy": 0.38}) if value == "recents" else (0.0, {})
		)

		# when
		results = magic_file_search(
			text_path,
			"new",
			search_names=False,
			search_contents=True,
		)

	# then
	assert len(results) == 1
	assert results[0].path == text_path
	assert results[0].score == pytest.approx(0.56)
	assert results[0].lines[0].location_kind == "line"
	assert results[0].lines[0].text == "recents"


def test_given_transcript_token_with_weak_semantic_when_scoring_then_does_not_rescue(tmp_path: Path):
	# given
	audio_path = tmp_path / "song.flac"
	audio_path.write_bytes(b"flac")

	with (
		patch(
			"srxy.file_search._iter_searchable_lines",
			return_value=[(40, "A little pace that they're focusing", "transcript")],
		),
		patch("srxy.file_search.CompositeMatcher") as composite_matcher,
		patch(
			"srxy.matchers.registry.is_matcher_available",
			lambda match_type: match_type == MatchType.SEMANTIC,
		),
	):
		composite_matcher.return_value.score_with_breakdown.side_effect = lambda q, value: (
			(0.297, {"semantic": 0.20, "fuzzy": 0.63}) if value == "focusing" else (0.0, {})
		)

		# when
		results = magic_file_search(
			tmp_path,
			"sibling",
			search_names=False,
			search_contents=True,
			threshold=0.18,
		)

	# then
	assert results == []
