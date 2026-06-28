from __future__ import annotations

import pytest

from srxy.utils import format_match_preview


pytestmark = pytest.mark.unit


def test_given_match_in_middle_of_long_text_when_formatting_preview_then_highlights_query():
	# given
	text = (
		"Daniel Illescas Romero universidadeuropea.com Predicción y prueba "
		"Se adjuntan los códigos para hacer más ameno el entrenamiento y predicción del modelo."
	)
	query = "entrenamiento"

	# when
	preview = format_match_preview(text, query, max_length=90)

	# then
	assert "«entrenamiento»" in preview
	assert "Predicción" in preview or "ameno" in preview


def test_given_short_text_when_formatting_preview_then_highlights_full_match():
	# given
	text = "quarterly revenue projections"
	query = "revenue"

	# when
	preview = format_match_preview(text, query)

	# then
	assert preview == "quarterly «revenue» projections"


def test_given_short_text_when_formatting_preview_with_bold_then_uses_rich_markup():
	# given
	text = "quarterly revenue projections"
	query = "revenue"

	# when
	preview = format_match_preview(text, query, highlight="bold")

	# then
	assert preview == "quarterly [bold]revenue[/bold] projections"


def test_given_short_text_when_formatting_preview_with_none_then_omits_highlight():
	# given
	text = "quarterly revenue projections"
	query = "revenue"

	# when
	preview = format_match_preview(text, query, highlight="none")

	# then
	assert preview == "quarterly revenue projections"


def test_given_related_word_when_formatting_preview_then_highlights_best_word_match():
	# given
	text = "Sister (=)"
	query = "sibling"

	# when
	preview = format_match_preview(text, query)

	# then
	assert preview == "«Sister» (=)"


def test_given_boolean_query_when_formatting_preview_then_highlights_matching_term_not_operator():
	# given
	text = "Mike Shinoda & Chester Bennington"
	query = '("linkin park" & "in the end")'

	# when
	preview = format_match_preview(text, query, highlight="bold")

	# then
	assert "[bold]&[/bold]" not in preview
	assert "[bold]in[/bold]" not in preview


def test_given_boolean_query_when_formatting_artist_tag_then_highlights_artist_name():
	# given
	text = "[Artist] Linkin Park"
	query = '("linkin park" & "in the end")'

	# when
	preview = format_match_preview(text, query, highlight="bold", highlight_term="linkin park")

	# then
	assert "[bold]Linkin[/bold]" in preview or "[bold]Linkin Park[/bold]" in preview
	assert "[bold]&[/bold]" not in preview


def test_given_lyrics_tag_when_formatting_with_matched_term_then_centers_phrase_match():
	# given
	text = (
		"[Lyrics] [Intro: Chester Bennington] It starts with one "
		"[Chorus: Chester Bennington] I tried so hard and got so far But in the end, it doesn't even matter"
	)
	query = '("linkin park" & "in the end")'

	# when
	preview = format_match_preview(text, query, highlight="bold", highlight_term="in the end")

	# then
	assert "[bold]in the end[/bold]" in preview
	assert "[bold]I[/bold]" not in preview
	assert "â" not in preview
