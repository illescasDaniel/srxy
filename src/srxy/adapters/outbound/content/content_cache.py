"""Content cache adapter for per-run file hashes."""

from __future__ import annotations

from pathlib import Path


class SqliteContentCache:
	"""ContentCachePort over the SQLite-backed content cache."""

	def get_file_content_hash(self, path: Path) -> str | None:
		from srxy.adapters.outbound.cache.cache import get_file_content_hash

		return get_file_content_hash(path)

	def reset_run_file_hashes(self):
		from srxy.adapters.outbound.cache.cache import reset_run_file_hashes

		reset_run_file_hashes()
