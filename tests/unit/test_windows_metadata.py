from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.windows_metadata import (
	iter_windows_metadata_lines,
	normalize_windows_keywords,
	windows_tags_supported,
)


pytestmark = pytest.mark.unit


def test_given_string_keyword_when_normalizing_then_returns_single_item():
	# when
	tags = normalize_windows_keywords("cursor")

	# then
	assert tags == ["cursor"]


def test_given_keyword_list_when_normalizing_then_returns_strings():
	# when
	tags = normalize_windows_keywords(["cursor", " quarterly ", None, ""])

	# then
	assert tags == ["cursor", "quarterly"]


def test_given_none_when_normalizing_then_returns_empty_list():
	# then
	assert normalize_windows_keywords(None) == []


def test_given_keyword_list_when_iterating_windows_lines_then_yields_tags(tmp_path: Path):
	# given
	file_path = tmp_path / "clip.mp4"

	# when
	with patch("srxy.windows_metadata._read_windows_keywords", return_value=["cursor", "quarterly"]):
		lines = list(iter_windows_metadata_lines(file_path))

	# then
	assert lines == [(1, "[Windows tag] cursor"), (2, "[Windows tag] quarterly")]


def test_given_property_store_error_when_reading_keywords_then_returns_empty(tmp_path: Path):
	# given
	file_path = tmp_path / "clip.mp4"

	# when
	with (
		patch("srxy.windows_metadata.windows_tags_supported", return_value=True),
		patch("srxy.windows_metadata._read_keywords_via_property_store", side_effect=OSError("access denied")),
	):
		tags = list(iter_windows_metadata_lines(file_path))

	# then
	assert tags == []


def test_given_non_windows_platform_when_checking_support_then_returns_false():
	# when
	with patch("srxy.windows_metadata.sys.platform", "linux"):
		supported = windows_tags_supported()

	# then
	assert supported is False
