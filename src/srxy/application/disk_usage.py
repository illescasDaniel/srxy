"""Directory / file size helpers for Settings maintenance UI."""

from __future__ import annotations

import os
from pathlib import Path

from srxy.application.size_limits import bytes_to_mib_text


_KIB = 1024
_MIB = 1024 * 1024


def path_size_bytes(path: Path) -> int:
	"""Return total size of a file or directory tree (no follow-symlinks)."""
	try:
		if not path.exists():
			return 0
	except OSError:
		return 0
	if path.is_file():
		try:
			return path.stat().st_size
		except OSError:
			return 0
	total = 0
	for root, _dirs, files in os.walk(path, followlinks=False):
		for name in files:
			try:
				total += (Path(root) / name).stat().st_size
			except OSError:
				continue
	return total


def format_byte_size(value: int) -> str:
	"""Human-readable size for Settings status lines."""
	if value < _KIB:
		return f"{value} B"
	if value < _MIB:
		kib = value / _KIB
		if kib == int(kib):
			return f"{int(kib)} KiB"
		return f"{kib:.1f}".rstrip("0").rstrip(".") + " KiB"
	return f"{bytes_to_mib_text(value)} MiB"


__all__ = ["format_byte_size", "path_size_bytes"]
