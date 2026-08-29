from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.adapters.inbound.cli.cli import format_skipped_file_warning, format_skipped_file_warnings
from srxy.adapters.outbound.content.file_walker import iter_files
from srxy.adapters.outbound.content.path_access import (
	PERMISSION_DENIED_REASON,
	directory_is_listable,
	is_access_denied,
)
from srxy.adapters.outbound.content.text_extractor import DefaultTextExtractor
from srxy.application.use_cases.search_files import FileSearchUseCase, set_text_extractor
from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ActivityCallback


pytestmark = pytest.mark.unit


def test_given_permission_error_when_checking_is_access_denied_then_true():
	assert is_access_denied(PermissionError(13, "Permission denied"))
	assert is_access_denied(OSError(13, "Permission denied"))
	denied = OSError("access denied")
	denied.winerror = 5  # type: ignore[attr-defined]
	assert is_access_denied(denied)
	assert is_access_denied(OSError(2, "No such file")) is False


def test_given_permission_denied_skip_when_formatting_warning_then_mentions_access_denied(tmp_path: Path):
	file_path = tmp_path / "secret.txt"
	file_path.write_text("x", encoding="utf-8")
	warning = format_skipped_file_warning(
		SkippedFile(path=file_path, size_bytes=0, reason=PERMISSION_DENIED_REASON),
		max_file_size=None,
	)
	assert "access denied" in warning
	assert file_path.as_posix() in warning


def test_given_duplicate_permission_skips_when_formatting_warnings_then_dedupes(tmp_path: Path):
	path = tmp_path / "locked"
	path.mkdir()
	skipped = [
		SkippedFile(path=path, size_bytes=0, reason=PERMISSION_DENIED_REASON),
		SkippedFile(path=path, size_bytes=0, reason=PERMISSION_DENIED_REASON),
	]
	text = format_skipped_file_warnings(skipped, max_file_size=None)
	assert text.count("access denied") == 1


def test_given_walk_onerror_when_iter_files_then_records_permission_skip(tmp_path: Path):
	root = tmp_path / "tree"
	root.mkdir()
	(root / "ok.txt").write_text("needle\n", encoding="utf-8")
	denied_dir = root / "locked"
	denied_dir.mkdir()
	(denied_dir / "hidden.txt").write_text("needle\n", encoding="utf-8")

	def fake_walk(
		path: str | Path,
		onerror: Callable[[OSError], None] | None = None,
		**_kwargs: object,
	):
		_ = path
		yield str(root), ["locked"], ["ok.txt"]
		if onerror is not None:
			onerror(PermissionError(13, "Permission denied", str(denied_dir)))

	skipped: list[SkippedFile] = []
	with patch("srxy.adapters.outbound.content.file_walker.os.walk", side_effect=fake_walk):
		paths = list(iter_files(root, skipped_files=skipped))

	assert paths == [root / "ok.txt"]
	assert len(skipped) == 1
	assert skipped[0].path == denied_dir
	assert skipped[0].reason == PERMISSION_DENIED_REASON


class _PermissionDeniedExtractor(DefaultTextExtractor):
	"""Raises PermissionError for selected basenames during content extraction."""

	def __init__(self, denied_names: set[str]):
		self.denied_names = denied_names
		self.opened: list[str] = []

	def iter_units(
		self,
		path: Path,
		max_file_size: int | None,
		*,
		search_docs_tags: bool = True,
		ocr: bool | None = None,
		transcribe: bool | None = None,
		skipped_files: list[SkippedFile] | None = None,
		on_activity: ActivityCallback | None = None,
	):
		self.opened.append(path.name)
		if path.name in self.denied_names:
			raise PermissionError(13, "Permission denied", str(path))
		yield from super().iter_units(
			path,
			max_file_size,
			search_docs_tags=search_docs_tags,
			ocr=ocr,
			transcribe=transcribe,
			skipped_files=skipped_files,
			on_activity=on_activity,
		)


def test_given_permission_error_on_file_when_searching_then_skips_and_continues(tmp_path: Path):
	allowed = tmp_path / "allowed.txt"
	denied = tmp_path / "denied.txt"
	allowed.write_text("needle here\n", encoding="utf-8")
	denied.write_text("needle here\n", encoding="utf-8")
	skipped: list[SkippedFile] = []
	extractor = _PermissionDeniedExtractor({"denied.txt"})
	set_text_extractor(extractor)
	try:
		results = FileSearchUseCase(text_extractor=extractor).search(
			tmp_path,
			"needle",
			search_names=False,
			skipped_files=skipped,
		)
	finally:
		set_text_extractor(None)

	assert len(results) == 1
	assert results[0].path.name == "allowed.txt"
	assert any(item.reason == PERMISSION_DENIED_REASON and item.path.name == "denied.txt" for item in skipped)


def test_given_unlistable_parent_when_file_denied_then_prunes_siblings(tmp_path: Path):
	parent = tmp_path / "locked_dir"
	parent.mkdir()
	first = parent / "a.txt"
	second = parent / "b.txt"
	first.write_text("needle\n", encoding="utf-8")
	second.write_text("needle\n", encoding="utf-8")
	outside = tmp_path / "outside.txt"
	outside.write_text("needle\n", encoding="utf-8")
	skipped: list[SkippedFile] = []
	extractor = _PermissionDeniedExtractor({"a.txt", "b.txt"})

	with patch(
		"srxy.application.use_cases.search_files.directory_is_listable",
		side_effect=lambda path: path != parent,
	):
		set_text_extractor(extractor)
		try:
			results = FileSearchUseCase(text_extractor=extractor).search(
				tmp_path,
				"needle",
				search_names=False,
				skipped_files=skipped,
			)
		finally:
			set_text_extractor(None)

	assert any(item.path.name == "outside.txt" for item in results)
	# First denied file triggers parent prune; sibling should not be opened.
	assert len([name for name in extractor.opened if name in {"a.txt", "b.txt"}]) == 1
	assert any(item.path == parent and item.reason == PERMISSION_DENIED_REASON for item in skipped)
	assert isinstance(results[0], FileSearchResult)


def test_given_listable_dir_when_checking_directory_is_listable_then_true(tmp_path: Path):
	assert directory_is_listable(tmp_path) is True


def test_given_missing_dir_when_checking_directory_is_listable_then_false(tmp_path: Path):
	assert directory_is_listable(tmp_path / "nope") is False
