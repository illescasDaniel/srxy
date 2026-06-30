from __future__ import annotations

import plistlib
from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.xattr_metadata import iter_xattr_metadata_lines


pytestmark = pytest.mark.unit

_FINDER_TAG_ATTR = "com.apple.metadata:_kMDItemUserTags"


def test_given_binary_plist_tags_when_iterating_xattr_lines_then_yields_finder_tags(tmp_path: Path):
	# given
	file_path = tmp_path / "file.txt"
	file_path.write_text("x", encoding="utf-8")
	raw = plistlib.dumps(["cursor", "Important\n6"], fmt=plistlib.FMT_BINARY)

	def fake_listxattr(path: Path, follow_symlinks: bool = False) -> list[str]:
		return [_FINDER_TAG_ATTR]

	def fake_getxattr(path: Path, name: str, follow_symlinks: bool = False) -> bytes:
		if name == _FINDER_TAG_ATTR:
			return raw
		raise OSError

	# when
	with (
		patch("srxy.xattr_metadata.xattr_supported", return_value=True),
		patch("srxy.xattr_metadata._listxattr", fake_listxattr),
		patch("srxy.xattr_metadata._getxattr", fake_getxattr),
	):
		lines = list(iter_xattr_metadata_lines(file_path))

	# then
	assert lines == [(1, "[Finder tag] cursor"), (2, "[Finder tag] Important")]


def test_given_invalid_plist_when_iterating_xattr_lines_then_yields_nothing(tmp_path: Path):
	# given
	file_path = tmp_path / "file.txt"
	file_path.write_text("x", encoding="utf-8")

	def fake_listxattr(path: Path, follow_symlinks: bool = False) -> list[str]:
		return [_FINDER_TAG_ATTR]

	def fake_getxattr(path: Path, name: str, follow_symlinks: bool = False) -> bytes:
		return b"not a plist"

	# when
	with (
		patch("srxy.xattr_metadata.xattr_supported", return_value=True),
		patch("srxy.xattr_metadata._listxattr", fake_listxattr),
		patch("srxy.xattr_metadata._getxattr", fake_getxattr),
	):
		lines = list(iter_xattr_metadata_lines(file_path))

	# then
	assert lines == []


def test_given_comma_separated_xdg_tags_when_iterating_xattr_lines_then_splits_values(tmp_path: Path):
	# given
	file_path = tmp_path / "file.txt"
	file_path.write_text("x", encoding="utf-8")

	def fake_listxattr(path: Path, follow_symlinks: bool = False) -> list[str]:
		return ["user.xdg.tags"]

	def fake_getxattr(path: Path, name: str, follow_symlinks: bool = False) -> bytes:
		return b"work, personal, archive"

	# when
	with (
		patch("srxy.xattr_metadata.xattr_supported", return_value=True),
		patch("srxy.xattr_metadata._listxattr", fake_listxattr),
		patch("srxy.xattr_metadata._getxattr", fake_getxattr),
	):
		lines = list(iter_xattr_metadata_lines(file_path))

	# then
	assert lines == [
		(1, "[XDG tag] work"),
		(2, "[XDG tag] personal"),
		(3, "[XDG tag] archive"),
	]


def test_given_xdg_comment_when_iterating_xattr_lines_then_yields_full_text(tmp_path: Path):
	# given
	file_path = tmp_path / "file.txt"
	file_path.write_text("x", encoding="utf-8")

	def fake_listxattr(path: Path, follow_symlinks: bool = False) -> list[str]:
		return ["user.xdg.comment"]

	def fake_getxattr(path: Path, name: str, follow_symlinks: bool = False) -> bytes:
		return b"mytag, with comma"

	# when
	with (
		patch("srxy.xattr_metadata.xattr_supported", return_value=True),
		patch("srxy.xattr_metadata._listxattr", fake_listxattr),
		patch("srxy.xattr_metadata._getxattr", fake_getxattr),
	):
		lines = list(iter_xattr_metadata_lines(file_path))

	# then
	assert lines == [(1, "[XDG comment] mytag, with comma")]


def test_given_finder_comment_when_iterating_xattr_lines_then_yields_full_text(tmp_path: Path):
	# given
	file_path = tmp_path / "file.txt"
	file_path.write_text("x", encoding="utf-8")

	def fake_listxattr(path: Path, follow_symlinks: bool = False) -> list[str]:
		return ["com.apple.metadata:kMDItemFinderComment"]

	def fake_getxattr(path: Path, name: str, follow_symlinks: bool = False) -> bytes:
		return b"project notes"

	# when
	with (
		patch("srxy.xattr_metadata.xattr_supported", return_value=True),
		patch("srxy.xattr_metadata._listxattr", fake_listxattr),
		patch("srxy.xattr_metadata._getxattr", fake_getxattr),
	):
		lines = list(iter_xattr_metadata_lines(file_path))

	# then
	assert lines == [(1, "[Finder comment] project notes")]


def test_given_binary_plist_finder_comment_when_iterating_xattr_lines_then_yields_plain_text(tmp_path: Path):
	# given
	file_path = tmp_path / "file.txt"
	file_path.write_text("x", encoding="utf-8")
	raw = plistlib.dumps("hello there", fmt=plistlib.FMT_BINARY)

	def fake_listxattr(path: Path, follow_symlinks: bool = False) -> list[str]:
		return ["com.apple.metadata:kMDItemFinderComment"]

	def fake_getxattr(path: Path, name: str, follow_symlinks: bool = False) -> bytes:
		return raw

	# when
	with (
		patch("srxy.xattr_metadata.xattr_supported", return_value=True),
		patch("srxy.xattr_metadata._listxattr", fake_listxattr),
		patch("srxy.xattr_metadata._getxattr", fake_getxattr),
	):
		lines = list(iter_xattr_metadata_lines(file_path))

	# then
	assert lines == [(1, "[Finder comment] hello there")]
