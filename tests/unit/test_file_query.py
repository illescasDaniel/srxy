from __future__ import annotations

import pytest

from srxy import FileQ
from srxy.file_query import (
	FileQueryParseError,
	build_file_query_from_rows,
	file_q_from_dict,
	file_q_to_dict,
	format_file_query,
	parse_file_query,
	query_highlight_terms,
	score_file_query,
)


pytestmark = pytest.mark.unit


def test_given_plain_term_when_parsing_query_then_returns_single_leaf():
	# given
	raw = "registry"

	# when
	expr = parse_file_query(raw)

	# then
	assert expr == FileQ.leaf("registry")


def test_given_or_expression_when_parsing_query_then_builds_or_tree():
	# given
	raw = "red|blue"

	# when
	expr = parse_file_query(raw)

	# then
	assert expr == FileQ.leaf("red") | FileQ.leaf("blue")


def test_given_unquoted_or_phrases_when_parsing_query_then_preserves_spaces_in_terms():
	# given
	raw = "Linkin Park|Call Me"

	# when
	expr = parse_file_query(raw)

	# then
	assert expr == FileQ.leaf("linkin park") | FileQ.leaf("call me")


def test_given_and_binds_tighter_than_or_when_parsing_query_then_groups_correctly():
	# given
	raw = "(red|blue|green)&color"

	# when
	expr = parse_file_query(raw)

	# then
	assert expr == (FileQ.leaf("red") | FileQ.leaf("blue") | FileQ.leaf("green")) & FileQ.leaf("color")


def test_given_quoted_phrase_when_parsing_query_then_preserves_spaces():
	# given
	raw = '"my search text"|other'

	# when
	expr = parse_file_query(raw)

	# then
	assert expr == FileQ.leaf("my search text") | FileQ.leaf("other")


def test_given_expression_when_formatting_then_round_trips():
	# given
	expr = (FileQ.leaf("red") | FileQ.leaf("blue")) & FileQ.leaf("color")

	# when
	formatted = format_file_query(expr)
	parsed = parse_file_query(formatted)

	# then
	assert parsed == expr


def test_given_nested_or_chain_when_formatting_then_flattens_operators():
	# given
	expr = ((FileQ.leaf("revenue") | FileQ.leaf("amphibian")) | FileQ.leaf("person")) | FileQ.leaf("thank you")

	# when
	formatted = format_file_query(expr)

	# then
	assert formatted == 'revenue | amphibian | person | "thank you"'


def test_given_uniform_or_rows_when_building_query_then_uses_flat_or_node():
	# given
	rows: list[tuple[str, str | None]] = [
		("revenue", None),
		("amphibian", "or"),
		("person", "or"),
		("thank you", "or"),
	]

	# when
	expr = build_file_query_from_rows(rows)

	# then
	assert expr == FileQ.any(
		FileQ.leaf("revenue"),
		FileQ.leaf("amphibian"),
		FileQ.leaf("person"),
		FileQ.leaf("thank you"),
	)


def test_given_term_scores_when_scoring_and_expression_then_uses_min():
	# given
	expr = FileQ.leaf("foo") & FileQ.leaf("bar")
	term_scores = {"foo": 0.9, "bar": 0.4}

	# when
	score = score_file_query(expr, term_scores)

	# then
	assert score == 0.4


def test_given_term_scores_when_scoring_or_expression_then_uses_max():
	# given
	expr = FileQ.leaf("foo") | FileQ.leaf("bar")
	term_scores = {"foo": 0.3, "bar": 0.8}

	# when
	score = score_file_query(expr, term_scores)

	# then
	assert score == 0.8


def test_given_builder_rows_when_building_query_then_left_associates_joins():
	# given
	rows: list[tuple[str, str | None]] = [("foo", None), ("bar", "and"), ("baz", "or")]

	# when
	expr = build_file_query_from_rows(rows)

	# then
	assert expr == (FileQ.leaf("foo") & FileQ.leaf("bar")) | FileQ.leaf("baz")


def test_given_plain_phrase_without_operators_when_parsing_query_then_keeps_whole_phrase():
	# given
	raw = "sunset beach"

	# when
	expr = parse_file_query(raw)

	# then
	assert expr == FileQ.leaf("sunset beach")


def test_given_boolean_query_when_extracting_highlight_terms_then_returns_leaves_only():
	# given
	raw = '("linkin park" & "in the end")'

	# when
	terms = query_highlight_terms(raw)

	# then
	assert terms == ["linkin park", "in the end"]


def test_given_invalid_query_when_parsing_then_raises_parse_error():
	# given
	raw = "(foo"

	# when
	with pytest.raises(FileQueryParseError):
		parse_file_query(raw)

	# then
	assert True


def test_given_expression_when_serializing_to_dict_then_round_trips():
	# given
	expr = FileQ.leaf("alpha") & FileQ.leaf("beta")

	# when
	restored = file_q_from_dict(file_q_to_dict(expr))

	# then
	assert restored == expr
