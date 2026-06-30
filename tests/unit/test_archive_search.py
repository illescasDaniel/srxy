from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from srxy.archive_search import (
	archive_member_path,
	is_standalone_archive,
	list_archive_members,
	split_archive_member_path,
)
from srxy.file_search import magic_file_search


pytestmark = pytest.mark.unit


def _write_zip(path: Path, members: dict[str, str]):
	buffer = io.BytesIO()
	with zipfile.ZipFile(buffer, "w") as archive:
		for name, content in members.items():
			archive.writestr(name, content)
	path.write_bytes(buffer.getvalue())


def _write_tar_gz(path: Path, members: dict[str, str]):
	buffer = io.BytesIO()
	with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
		for name, content in members.items():
			data = content.encode("utf-8")
			info = tarfile.TarInfo(name=name)
			info.size = len(data)
			archive.addfile(info, io.BytesIO(data))
	path.write_bytes(buffer.getvalue())


def test_given_zip_with_text_member_when_include_archives_disabled_then_skips_inner_file(tmp_path: Path):
	# given
	_write_zip(tmp_path / "bundle.zip", {"notes.txt": "quarterly revenue inside zip"})
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, include_archives=False)

	# then
	assert results == []


def test_given_zip_with_text_member_when_include_archives_enabled_then_finds_inner_content(tmp_path: Path):
	# given
	_write_zip(tmp_path / "bundle.zip", {"notes.txt": "quarterly revenue inside zip"})
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, include_archives=True)

	# then
	assert len(results) == 1
	member_path = results[0].path.as_posix()
	assert member_path.endswith("bundle.zip::notes.txt")
	assert results[0].breakdown["content"] >= 0.25
	assert any("revenue" in line.text for line in results[0].lines)


def test_given_tar_gz_with_text_member_when_include_archives_enabled_then_finds_inner_content(tmp_path: Path):
	# given
	_write_tar_gz(tmp_path / "backup.tar.gz", {"data/report.txt": "annual revenue summary"})
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, include_archives=True)

	# then
	assert len(results) == 1
	assert "backup.tar.gz::data/report.txt" in results[0].path.as_posix()
	assert any("revenue" in line.text for line in results[0].lines)


def test_given_docx_file_when_include_archives_enabled_then_does_not_expand_office_zip(tmp_path: Path):
	# given
	_write_zip(tmp_path / "report.docx", {"word/document.xml": "<w:document/>"})
	query = "report"

	# when
	results = magic_file_search(tmp_path, query, search_names=True, search_contents=False, include_archives=True)

	# then
	assert len(results) == 1
	assert results[0].path.name == "report.docx"
	assert "::" not in results[0].path.as_posix()


def test_given_archive_helpers_when_splitting_member_path_then_returns_parts(tmp_path: Path):
	# given
	archive = tmp_path / "files.zip"
	member = archive_member_path(archive, "inner/readme.txt")

	# when
	archive_path, inner = split_archive_member_path(member)

	# then
	assert archive_path == archive
	assert inner == "inner/readme.txt"
	assert is_standalone_archive(archive) is False
	_write_zip(archive, {"inner/readme.txt": "hello"})
	assert is_standalone_archive(archive)
	assert list_archive_members(archive) == ["inner/readme.txt"]
