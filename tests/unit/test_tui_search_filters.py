from __future__ import annotations

import pytest

from srxy.cli import build_parser
from srxy.tui.search_filters import (
	SearchFilters,
	apply_search_filters_to_args,
	format_search_filters_summary,
	search_filters_from_args,
	validate_search_filters,
)
from srxy.tui.size_limits import SizeLimits


pytestmark = pytest.mark.unit


def test_given_default_args_when_building_search_filters_then_reflects_values():
	# given
	args = build_parser().parse_args(["token"])

	# when
	filters = search_filters_from_args(args)

	# then
	assert filters.top_files == ""
	assert filters.max_matches == "50"
	assert filters.size_limits == SizeLimits(text_mib="100", ocr_mib="50", transcribe_mib="500")


def test_given_limit_and_size_flags_when_building_search_filters_then_reflects_arguments():
	# given
	args = build_parser().parse_args(
		[
			"token",
			"-l",
			"10",
			"--max-matches",
			"25",
			"--max-file-size",
			"0",
		]
	)

	# when
	filters = search_filters_from_args(args)

	# then
	assert filters.top_files == "10"
	assert filters.max_matches == "25"
	assert filters.size_limits.text_mib == "0"


def test_given_search_filters_when_applying_to_args_then_sets_namespace_fields():
	# given
	args = build_parser().parse_args(["token"])
	filters = SearchFilters(
		top_files="5",
		max_matches="12",
		size_limits=SizeLimits(text_mib="10", ocr_mib="20", transcribe_mib="30"),
	)

	# when
	apply_search_filters_to_args(args, filters)

	# then
	assert args.limit == 5
	assert args.max_matches == 12
	assert args.max_file_size == 10 * 1024 * 1024


def test_given_invalid_top_files_when_validating_then_raises():
	# given
	filters = SearchFilters(
		top_files="abc",
		max_matches="50",
		size_limits=SizeLimits(text_mib="100", ocr_mib="50", transcribe_mib="500"),
	)

	# when / then
	with pytest.raises(ValueError, match="Top files"):
		validate_search_filters(filters)


def test_given_enabled_filters_when_formatting_summary_then_includes_top_n():
	# given
	filters = SearchFilters(
		top_files="10",
		max_matches="25",
		size_limits=SizeLimits(text_mib="0", ocr_mib="50", transcribe_mib="500"),
	)

	# when
	summary = format_search_filters_summary(filters)

	# then
	assert "Top 10" in summary
	assert "25/file" in summary
	assert "0 MiB" in summary
