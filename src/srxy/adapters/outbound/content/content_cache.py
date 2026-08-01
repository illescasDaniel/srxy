"""Content cache adapter for per-run file hashes."""

from __future__ import annotations

from pathlib import Path

from srxy.adapters.outbound.cache.cache import (
	get_file_content_hash as _get_file_content_hash,
	reset_run_file_hashes as _reset_run_file_hashes,
)


class SqliteContentCache:
	"""ContentCachePort over the SQLite-backed content cache."""

	def get_file_content_hash(self, path: Path) -> str | None:
		return _get_file_content_hash(path)

	def reset_run_file_hashes(self):
		_reset_run_file_hashes()
