from __future__ import annotations

from pathlib import Path

import pytest
from tests.helpers import file_search_root, require_file_search_fixtures

from srxy.file_query import format_query_for_display
from srxy.file_search import magic_file_search
from srxy.utils import format_match_preview


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


@pytest.mark.transcribe
def test_given_far_cry_query_when_searching_unrelated_audio_then_does_not_match():
	# given — single known false-positive candidate; avoid transcribing the whole corpus
	require_file_search_fixtures()
	audio = file_search_root() / "minimal.mp3"
	assert audio.is_file(), f"missing QA audio fixture: {audio}"

	# when
	results = magic_file_search(audio, "far cry", threshold=0.35, transcribe=True, limit=10)

	# then
	assert results == []


def test_given_quoted_query_display_when_formatting_status_then_avoids_double_quotes():
	# when / then
	assert format_query_for_display('"far cry"') == "far cry"
	assert format_query_for_display("far cry") == "far cry"


def test_given_boolean_query_display_when_formatting_status_then_preserves_expression():
	# when / then
	assert format_query_for_display("far | cry") == "far | cry"
