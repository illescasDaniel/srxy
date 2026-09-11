"""Unit tests for disk usage helpers used by Settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.application.disk_usage import format_byte_size, path_size_bytes


pytestmark = pytest.mark.unit


def test_given_missing_path_when_sizing_then_returns_zero(tmp_path: Path):
	# given
	missing = tmp_path / "nope"

	# when
	size = path_size_bytes(missing)

	# then
	assert size == 0


def test_given_file_and_directory_when_sizing_then_sums_bytes(tmp_path: Path):
	# given
	file_path = tmp_path / "a.bin"
	file_path.write_bytes(b"x" * 100)
	nested = tmp_path / "dir" / "b.bin"
	nested.parent.mkdir()
	nested.write_bytes(b"y" * 50)

	# when / then
	assert path_size_bytes(file_path) == 100
	assert path_size_bytes(tmp_path / "dir") == 50
	assert path_size_bytes(tmp_path) == 150


def test_given_byte_counts_when_formatting_then_uses_human_units():
	# given / when / then
	assert format_byte_size(0) == "0 B"
	assert format_byte_size(512) == "512 B"
	assert format_byte_size(2048) == "2 KiB"
	assert format_byte_size(1024 * 1024) == "1 MiB"
	assert format_byte_size(int(1.5 * 1024 * 1024)) == "1.5 MiB"
