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
