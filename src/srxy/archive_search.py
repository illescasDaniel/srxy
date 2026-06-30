from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

from srxy.archive_guard import ArchiveGuardError, validate_archive_members
from srxy.document_text import DOCUMENT_SUFFIXES


ARCHIVE_MEMBER_SEP = "::"

_ARCHIVE_SUFFIXES = (
	".tar.gz",
	".tar.bz2",
	".tar.xz",
	".tgz",
	".tbz2",
	".txz",
	".zip",
	".tar",
	".gz",
)


def archive_member_path(archive: Path, member: str) -> Path:
	return Path(f"{archive.as_posix()}{ARCHIVE_MEMBER_SEP}{member}")


def split_archive_member_path(path: Path) -> tuple[Path, str | None]:
	text = path.as_posix()
	separator = text.find(ARCHIVE_MEMBER_SEP)
	if separator < 0:
		return path, None
	return Path(text[:separator]), text[separator + len(ARCHIVE_MEMBER_SEP) :]


def is_archive_member_path(path: Path) -> bool:
	return ARCHIVE_MEMBER_SEP in path.as_posix()


def is_searchable_path(path: Path) -> bool:
	archive_path, member = split_archive_member_path(path)
	if member is not None:
		return archive_path.is_file()
	return path.is_file()


def _archive_suffix(path: Path) -> str | None:
	name = path.name.lower()
	for suffix in _ARCHIVE_SUFFIXES:
		if name.endswith(suffix):
			return suffix
	return None


def is_standalone_archive(path: Path) -> bool:
	if not path.is_file():
		return False
	if path.suffix.lower() in DOCUMENT_SUFFIXES:
		return False
	return _archive_suffix(path) is not None


def _member_is_file(name: str) -> bool:
	normalized = name.rstrip("/")
	return bool(normalized) and not normalized.endswith("/")


def _list_zip_members(path: Path) -> list[str]:
	with zipfile.ZipFile(path) as archive:
		members = [(info.filename, info.file_size) for info in archive.infolist() if _member_is_file(info.filename)]
	validate_archive_members(members)
	return [name for name, _size in members]


def _list_tar_members(path: Path) -> list[str]:
	members: list[tuple[str, int]] = []
	with tarfile.open(path) as archive:
		for member in archive.getmembers():
			if not member.isfile():
				continue
			members.append((member.name, member.size))
	validate_archive_members(members)
	return [name for name, _size in members]


def _list_gzip_member(path: Path) -> list[str]:
	with gzip.open(path, "rb") as handle:
		handle.read(1)
	return [path.stem or path.name.removesuffix(".gz")]


def list_archive_members(path: Path) -> list[str]:
	suffix = _archive_suffix(path)
	if suffix is None:
		return []
	try:
		if suffix == ".zip":
			return _list_zip_members(path)
		if suffix == ".gz" and not path.name.lower().endswith(".tar.gz"):
			return _list_gzip_member(path)
		return _list_tar_members(path)
	except (OSError, zipfile.BadZipFile, tarfile.TarError, gzip.BadGzipFile, ArchiveGuardError):
		return []


def archive_member_size_bytes(path: Path) -> int | None:
	archive_path, member = split_archive_member_path(path)
	if member is None:
		return None
	suffix = _archive_suffix(archive_path)
	if suffix is None:
		return None
	try:
		if suffix == ".zip":
			with zipfile.ZipFile(archive_path) as archive:
				info = archive.getinfo(member)
				return info.file_size
		if suffix == ".gz" and not archive_path.name.lower().endswith(".tar.gz"):
			with gzip.open(archive_path, "rb") as handle:
				handle.seek(0, io.SEEK_END)
				return handle.tell()
		with tarfile.open(archive_path) as archive:
			entry = archive.getmember(member)
			return entry.size
	except (OSError, KeyError, zipfile.BadZipFile, tarfile.TarError, gzip.BadGzipFile):
		return None


def read_archive_member_bytes(path: Path, *, max_bytes: int | None = None) -> bytes | None:
	archive_path, member = split_archive_member_path(path)
	if member is None:
		return None
	suffix = _archive_suffix(archive_path)
	if suffix is None:
		return None
	try:
		if suffix == ".zip":
			with zipfile.ZipFile(archive_path) as archive:
				with archive.open(member) as handle:
					if max_bytes is None:
						return handle.read()
					return handle.read(max_bytes + 1)
		if suffix == ".gz" and not archive_path.name.lower().endswith(".tar.gz"):
			with gzip.open(archive_path, "rb") as handle:
				if max_bytes is None:
					return handle.read()
				return handle.read(max_bytes + 1)
		with tarfile.open(archive_path) as archive:
			entry = archive.extractfile(member)
			if entry is None:
				return None
			with entry as handle:
				if max_bytes is None:
					return handle.read()
				return handle.read(max_bytes + 1)
	except (OSError, KeyError, zipfile.BadZipFile, tarfile.TarError, gzip.BadGzipFile):
		return None


def _archive_member_within_size_limit(path: Path, max_file_size: int | None) -> bool:
	if max_file_size is None:
		return True
	size = archive_member_size_bytes(path)
	if size is None:
		return False
	if size == 0:
		return True
	return size <= max_file_size


def _is_probably_text_bytes(sample: bytes) -> bool:
	return b"\x00" not in sample


def iter_archive_member_lines(
	path: Path,
	max_file_size: int | None,
) -> Iterator[tuple[int, str]]:
	if not _archive_member_within_size_limit(path, max_file_size):
		return
	read_limit = None if max_file_size is None else max_file_size + 1
	payload = read_archive_member_bytes(path, max_bytes=read_limit)
	if payload is None:
		return
	if max_file_size is not None and len(payload) > max_file_size:
		return
	if not _is_probably_text_bytes(payload[: min(len(payload), 8192)]):
		return
	text = payload.decode("utf-8", errors="ignore")
	bytes_read = 0
	for line_number, raw_line in enumerate(text.splitlines(), start=1):
		if max_file_size is not None:
			bytes_read += len(raw_line.encode("utf-8", errors="ignore"))
			if bytes_read > max_file_size:
				break
		yield line_number, raw_line.rstrip("\n\r")
