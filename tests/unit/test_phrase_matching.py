from __future__ import annotations

from pathlib import Path

import pytest

from srxy.application.use_cases.search_files import magic_file_search
from srxy.application.utils import format_match_preview
from srxy.domain.file_query import format_query_for_display


pytestmark = pytest.mark.unit


def test_given_multi_word_query_when_scoring_transcript_without_cry_then_does_not_match(tmp_path: Path):
	# given
	text_file = tmp_path / "lyrics.txt"
	text_file.write_text("And got so far, let me in, it doesn't even matter.")

	# when
	results = magic_file_search(tmp_path, "far cry", threshold=0.1, search_names=False)

	# then
	assert results == []


def test_given_multi_word_query_when_formatting_preview_then_highlights_matching_words_not_fuzzy_noise():
	# given
	text = "[Lyrics] Time is a valuable thing Watch it fly by as the pendulum swings"
	query = "far cry"

	# when
	preview = format_match_preview(text, query, highlight="bold")

	# then
	assert "[bold]" not in preview


def test_given_multi_word_query_when_formatting_transcript_preview_then_highlights_far():
	# given
	text = "And got so far, let me in, it doesn't even matter."
	query = "far cry"

	# when
	preview = format_match_preview(text, query, highlight="bold")

	# then
	assert "[bold]far[/bold]" in preview


def test_given_quoted_query_display_when_formatting_status_then_avoids_double_quotes():
	# when / then
	assert format_query_for_display('"far cry"') == "far cry"
	assert format_query_for_display("far cry") == "far cry"


def test_given_boolean_query_display_when_formatting_status_then_preserves_expression():
	# when / then
	assert format_query_for_display("far | cry") == "far | cry"
