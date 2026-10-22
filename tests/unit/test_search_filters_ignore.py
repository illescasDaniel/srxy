from __future__ import annotations

import argparse
from dataclasses import replace

import pytest

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.application.search_filters import (
	SearchFilters,
	apply_search_filters_to_args,
	default_search_filters,
	format_search_filters_summary,
	ignore_lines,
	ignore_spec_from_args,
	search_filters_from_args,
	validate_ignore_text,
	validate_search_filters,
)
from srxy.domain.ignore_rules import IgnoreSpec


pytestmark = pytest.mark.unit


def _filters(ignore_patterns: str = "", respect_gitignore: bool = False) -> SearchFilters:
	return replace(default_search_filters(), ignore_patterns=ignore_patterns, respect_gitignore=respect_gitignore)


def test_given_default_filters_when_reset_then_ignore_list_empty_and_gitignore_off():
	# given / when
	filters = default_search_filters()

	# then
	assert filters.ignore_patterns == ""
	assert filters.respect_gitignore is False


def test_given_text_with_blanks_and_comments_when_ignore_lines_then_lines_kept_raw():
	# given
	filters = _filters("a\n\n# note\nb")

	# when
	lines = ignore_lines(filters)

	# then
	assert lines == ["a", "", "# note", "b"]


def test_given_empty_text_when_ignore_lines_then_empty_list():
	# given / when / then
	assert ignore_lines(_filters("")) == []


def test_given_unclosed_bracket_on_line_two_when_validate_ignore_text_then_message_names_line():
	# given
	text = "*.log\n[oops"

	# when
	message = validate_ignore_text(text)

	# then
	assert message != ""
	assert "2" in message


def test_given_valid_text_when_validate_ignore_text_then_empty_string():
	# given
	text = "# note\n\n*.log\n!keep.log\n/src/old/"

	# when / then
	assert validate_ignore_text(text) == ""


def test_given_trailing_backslash_when_validate_ignore_text_then_message_names_line():
	# given
	text = "ok\nok2\nbad\\"

	# when
	message = validate_ignore_text(text)

	# then
	assert message != ""
	assert "3" in message


def test_given_invalid_pattern_when_validate_search_filters_then_value_error_names_line():
	# given
	filters = _filters("a\n[oops")

	# when / then
	with pytest.raises(ValueError, match="2"):
		validate_search_filters(filters)


def test_given_valid_patterns_when_validate_search_filters_then_passes():
	# given
	filters = _filters("*.log\n!keep.log", respect_gitignore=True)

	# when / then
	validate_search_filters(filters)


def test_given_1000_lines_when_validate_ignore_text_then_ok():
	# given
	text = "\n".join(["x"] * 1000)

	# when / then
	assert validate_ignore_text(text) == ""


def test_given_1001_lines_when_validate_ignore_text_then_error():
	# given
	text = "\n".join(["x"] * 1001)

	# when
	message = validate_ignore_text(text)

	# then
	assert message != ""


def test_given_1001_lines_when_validate_search_filters_then_value_error():
	# given
	filters = _filters("\n".join(["x"] * 1001))

	# when / then
	with pytest.raises(ValueError):
		validate_search_filters(filters)


def test_given_line_of_1024_chars_when_validate_ignore_text_then_ok():
	# given
	text = "a" * 1024

	# when / then
	assert validate_ignore_text(text) == ""


def test_given_line_over_1024_chars_when_validate_ignore_text_then_error_names_line():
	# given
	text = "ok\n" + "a" * 1025

	# when
	message = validate_ignore_text(text)

	# then
	assert message != ""
	assert "2" in message


def test_given_line_over_1024_chars_when_validate_search_filters_then_value_error():
	# given
	filters = _filters("a" * 1025)

	# when / then
	with pytest.raises(ValueError):
		validate_search_filters(filters)


def test_given_filters_with_ignore_when_apply_to_args_then_sets_list_and_checkbox():
	# given
	args = build_parser().parse_args(["token"])
	filters = _filters("*.log\n!keep.log", respect_gitignore=True)

	# when
	apply_search_filters_to_args(args, filters)

	# then
	assert args.ignore == ["*.log", "!keep.log"]
	assert args.respect_gitignore is True


def test_given_empty_ignore_when_apply_to_args_then_empty_list_and_gitignore_off():
	# given
	args = build_parser().parse_args(["token"])

	# when
	apply_search_filters_to_args(args, _filters())

	# then
	assert args.ignore == []
	assert args.respect_gitignore is False


def test_given_filters_applied_to_args_when_search_filters_from_args_then_round_trips():
	# given
	args = build_parser().parse_args(["token"])
	filters = _filters("*.log\n\n# note\n/src/old/", respect_gitignore=True)
	apply_search_filters_to_args(args, filters)

	# when
	rebuilt = search_filters_from_args(args)

	# then
	assert rebuilt.ignore_patterns == filters.ignore_patterns
	assert rebuilt.respect_gitignore is True


def test_given_args_without_ignore_attrs_when_ignore_spec_from_args_then_inactive():
	# given
	args = argparse.Namespace()

	# when
	spec = ignore_spec_from_args(args)

	# then
	assert spec is None or not spec.active


def test_given_args_with_none_ignore_when_ignore_spec_from_args_then_inactive():
	# given
	args = argparse.Namespace(ignore=None, respect_gitignore=False)

	# when
	spec = ignore_spec_from_args(args)

	# then
	assert spec is None or not spec.active


def test_given_args_with_ignore_when_ignore_spec_from_args_then_spec_carries_values():
	# given
	args = argparse.Namespace(ignore=["a", "!b"], respect_gitignore=True)

	# when
	spec = ignore_spec_from_args(args)

	# then
	assert spec == IgnoreSpec(patterns=("a", "!b"), respect_gitignore=True)


def test_given_three_patterns_and_gitignore_when_format_summary_then_reads_ignoring_3_patterns():
	# given
	filters = _filters("a\nb\nc", respect_gitignore=True)

	# when
	summary = format_search_filters_summary(filters)

	# then
	assert "ignoring 3 patterns (+.gitignore)" in summary


def test_given_gitignore_on_and_empty_list_when_format_summary_then_reads_gitignore_only():
	# given
	filters = _filters("", respect_gitignore=True)

	# when
	summary = format_search_filters_summary(filters)

	# then
	assert "ignoring .gitignore matches" in summary
	assert "patterns" not in summary


def test_given_comments_and_blanks_when_format_summary_then_counts_effective_patterns_only():
	# given
	filters = _filters("a\n\n# note\nb\nc")

	# when
	summary = format_search_filters_summary(filters)

	# then
	assert "ignoring 3 patterns" in summary
	assert ".gitignore" not in summary


def test_given_no_ignore_when_format_summary_then_no_ignoring_text():
	# given
	filters = _filters()

	# when
	summary = format_search_filters_summary(filters)

	# then
	assert "ignoring" not in summary
	assert ".gitignore" not in summary
