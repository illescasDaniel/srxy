from __future__ import annotations

from pathlib import Path
from typing import BinaryIO
from unittest.mock import patch

import pytest

from srxy.media_metadata import is_media_path, iter_media_metadata_lines


pytestmark = pytest.mark.unit


def test_given_arw_suffix_when_checking_media_path_then_returns_true():
	# given
	path = Path("/photos/DSC02995.ARW")

	# when / then
	assert is_media_path(path) is True


def test_given_exifread_tags_when_iterating_metadata_lines_then_maps_make_and_model(tmp_path: Path):
	# given
	raw_file = tmp_path / "photo.arw"
	raw_file.write_bytes(b"\x00")

	class FakeTag:
		def __init__(self, value: str):
			self._value = value

		def __str__(self) -> str:
			return self._value

	def fake_process_file(handle: BinaryIO, details: bool = False):
		return {
			"Image Make": FakeTag("SONY"),
			"Image Model": FakeTag("ILCE-7C"),
			"JPEGThumbnail": FakeTag("skip me"),
		}

	# when
	with patch("exifread.process_file", fake_process_file):
		lines = list(iter_media_metadata_lines(raw_file))

	# then
	assert "[Make] SONY" in lines[0][1]
	assert any("[Model] ILCE-7C" in line[1] for line in lines)
