"""Helpers for filesystem access-denied (EACCES / Error 13) handling."""

from __future__ import annotations

import errno
import os
from pathlib import Path

from srxy.domain.models import SkippedFile


PERMISSION_DENIED_REASON = "permission_denied"

# Windows ERROR_ACCESS_DENIED
_WINERROR_ACCESS_DENIED = 5


def is_access_denied(exc: BaseException) -> bool:
	"""True for PermissionError / EACCES / EPERM / Windows access denied."""
	if isinstance(exc, PermissionError):
		return True
	if isinstance(exc, OSError):
		if exc.errno in {errno.EACCES, errno.EPERM}:
			return True
		winerror = getattr(exc, "winerror", None)
		if winerror == _WINERROR_ACCESS_DENIED:
			return True
	return False


def directory_is_listable(path: Path) -> bool:
	"""Return False when the directory cannot be listed due to permissions."""
	try:
		os.listdir(path)
	except OSError as exc:
		if is_access_denied(exc):
			return False
		return False
	return True


def permission_skip(path: Path) -> SkippedFile:
	return SkippedFile(path=path, size_bytes=0, reason=PERMISSION_DENIED_REASON)


def append_permission_skip(skipped_files: list[SkippedFile] | None, path: Path) -> SkippedFile | None:
	if skipped_files is None:
		return None
	skipped = permission_skip(path)
	skipped_files.append(skipped)
	return skipped
