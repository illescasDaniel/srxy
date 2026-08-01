from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from srxy.adapters.inbound.tui.labels import format_tui_match_labels
from srxy.application.search_options import (
	SearchOptions,
	apply_search_options_to_args,
	format_search_options_summary,
	has_search_source,
	search_options_from_args,
)
from srxy.domain.models import FileSearchResult, LineMatch


pytestmark = pytest.mark.unit


def test_given_args_when_building_search_options_then_reflects_flags():
	# given
	args = argparse.Namespace(
		names_only=False,
		content_only=False,
		search_names=True,
		search_contents=True,
		search_docs_tags=False,
		semantic=False,
		semantic_image=False,
		semantic_all=False,
		ocr=False,
		transcribe=False,
		include_hidden=True,
		include_noise=False,
		include_archives=True,
		include_subdirectories=False,
	)

	# when
	options = search_options_from_args(args)

	# then
	assert options == SearchOptions(
		search_names=True,
		search_contents=True,
		search_docs_tags=False,
		include_hidden=True,
		include_archives=True,
		include_subdirectories=False,
	)


def test_given_search_options_when_applying_to_args_then_sets_include_archives():
	# given
	args = argparse.Namespace(
		names_only=False,
		content_only=False,
		search_names=True,
		search_contents=True,
		search_docs_tags=True,
		semantic=False,
		semantic_image=False,
		semantic_all=False,
		ocr=False,
		transcribe=False,
		include_hidden=False,
		include_noise=False,
		include_archives=False,
		include_subdirectories=True,
	)
	options = SearchOptions(include_archives=True, ocr=True, include_subdirectories=False)

	# when
	apply_search_options_to_args(args, options)

	# then
	assert args.include_archives is True
	assert args.ocr is True
	assert args.include_subdirectories is False
	assert args.search_docs_tags is True


def test_given_enabled_options_when_formatting_summary_then_lists_labels():
	# given
	options = SearchOptions(search_names=True, search_contents=True, include_archives=True)

	# when
	summary = format_search_options_summary(options)

	# then
	assert summary == "Where: Names, Content · How: Docs & tags · Scan: Archives"


def test_given_top_level_only_when_formatting_summary_then_lists_scan_label():
	# given
	options = SearchOptions(search_names=True, search_contents=True, include_subdirectories=False)

	# when
	summary = format_search_options_summary(options)

	# then
	assert summary == "Where: Names, Content · How: Docs & tags · Scan: This folder only"


def test_given_powerups_when_formatting_summary_then_shows_how_segment():
	# given
	options = SearchOptions(
		search_names=True,
		search_contents=True,
		ocr=True,
		transcribe=True,
	)

	# when
	summary = format_search_options_summary(options)

	# then
	assert summary == "Where: Names, Content · How: Docs & tags, Image text, Speech"


def test_given_ocr_only_how_when_formatting_summary_then_omits_docs_tags():
	# given
	options = SearchOptions(
		search_names=False,
		search_contents=True,
		search_docs_tags=False,
		ocr=True,
	)

	# when
	summary = format_search_options_summary(options)

	# then
	assert summary == "Where: Content · How: Image text"
	assert has_search_source(options)


def test_given_contents_off_with_preferred_how_ticks_when_formatting_summary_then_hides_how():
	# given
	options = SearchOptions(
		search_names=True,
		search_contents=False,
		search_docs_tags=True,
		ocr=True,
		transcribe=True,
		semantic_image=True,
	)

	# when
	summary = format_search_options_summary(options)

	# then
	assert summary == "Where: Names"
	assert options.ocr is True
	assert options.search_docs_tags is True
	assert not has_search_source(SearchOptions(search_names=False, search_contents=False, ocr=True))


def test_given_contents_off_when_applying_options_to_args_then_preserves_preferred_how_ticks():
	# given
	args = argparse.Namespace(
		names_only=False,
		content_only=False,
		search_names=True,
		search_contents=True,
		search_docs_tags=True,
		semantic=False,
		semantic_image=False,
		semantic_all=False,
		ocr=False,
		transcribe=False,
		include_hidden=False,
		include_noise=False,
		include_archives=False,
		include_subdirectories=True,
	)
	options = SearchOptions(
		search_names=True,
		search_contents=False,
		search_docs_tags=True,
		ocr=True,
		transcribe=True,
	)

	# when
	apply_search_options_to_args(args, options)

	# then
	assert args.search_contents is False
	assert args.search_docs_tags is True
	assert args.ocr is True
	assert args.transcribe is True


def test_given_match_labels_when_formatting_for_tui_then_uses_plain_language():
	# given
	result = FileSearchResult(
		path=Path(__file__),
		score=0.9,
		breakdown={"name": 0.4, "ocr": 0.9, "transcript": 0.5},
		lines=[
			LineMatch(line_number=1, text="invoice", score=0.9, location_kind="ocr"),
			LineMatch(line_number=30, text="thanks", score=0.5, location_kind="transcript"),
		],
	)

	# when
	labels = format_tui_match_labels(result, threshold=0.35, transcribe_threshold=0.25)

	# then
	assert labels == "filename, image text, speech"
