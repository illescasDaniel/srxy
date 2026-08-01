from __future__ import annotations

import zipfile
from pathlib import Path


MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


class ArchiveGuardError(ValueError):
	"""Raised when an office archive exceeds safe extraction limits."""


def validate_archive_members(members: list[tuple[str, int]]):
	if len(members) > MAX_ZIP_ENTRIES:
		raise ArchiveGuardError("too many archive entries")
	uncompressed = 0
	for _name, size in members:
		uncompressed += size
		if uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
			raise ArchiveGuardError("uncompressed archive size too large")


def validate_zip_archive(path: Path):
	with zipfile.ZipFile(path) as archive:
		entries = archive.infolist()
		members = [(info.filename, info.file_size) for info in entries]
	validate_archive_members(members)
