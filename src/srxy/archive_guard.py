from __future__ import annotations

import zipfile
from pathlib import Path


MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


class ArchiveGuardError(ValueError):
	"""Raised when an office archive exceeds safe extraction limits."""


def validate_zip_archive(path: Path):
	with zipfile.ZipFile(path) as archive:
		entries = archive.infolist()
		if len(entries) > MAX_ZIP_ENTRIES:
			raise ArchiveGuardError(f"too many entries in {path.name}")
		uncompressed = 0
		for info in entries:
			uncompressed += info.file_size
			if uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
				raise ArchiveGuardError(f"uncompressed size too large in {path.name}")
