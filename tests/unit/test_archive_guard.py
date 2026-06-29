from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from srxy.archive_guard import ArchiveGuardError, validate_zip_archive


pytestmark = pytest.mark.unit


def _write_zip(path: Path, *, entries: int = 1, entry_size: int = 16):
	buffer = io.BytesIO()
	with zipfile.ZipFile(buffer, "w") as archive:
		for index in range(entries):
			archive.writestr(f"entry-{index}.txt", "x" * entry_size)
	path.write_bytes(buffer.getvalue())


def test_given_small_zip_when_validating_then_passes(tmp_path: Path):
	# given
	path = tmp_path / "sample.docx"
	_write_zip(path)

	# when / then
	validate_zip_archive(path)


def test_given_too_many_entries_when_validating_then_raises(tmp_path: Path):
	# given
	path = tmp_path / "large.docx"
	_write_zip(path, entries=10_001)

	# when / then
	with pytest.raises(ArchiveGuardError):
		validate_zip_archive(path)
