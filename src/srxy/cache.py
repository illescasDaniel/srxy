from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path


CACHE_KIND_OCR_IMAGE = "ocr_image"
CACHE_KIND_OCR_PDF_BLOB = "ocr_pdf_blob"
CACHE_KIND_CLIP_EMBED = "clip_embed"
CACHE_KIND_TRANSCRIPT = "transcript"

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})
_SCHEMA_VERSION = 1

_connection: sqlite3.Connection | None = None
_run_file_hashes: dict[Path, str] = {}


def cache_disabled() -> bool:
	value = os.environ.get("SRXY_CACHE_DISABLE", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def cache_db_path() -> Path:
	raw = os.environ.get("SRXY_CACHE_DIR", "").strip()
	if raw:
		return Path(raw).expanduser() / "cache.db"
	return Path.home() / ".cache" / "srxy" / "cache.db"


def cache_max_bytes() -> int | None:
	raw = os.environ.get("SRXY_CACHE_MAX_BYTES", "").strip()
	if not raw:
		return None
	try:
		return int(raw)
	except ValueError:
		return None


def hash_bytes(data: bytes) -> str:
	return hashlib.blake2b(data, digest_size=32).hexdigest()


def hash_file(path: Path) -> str:
	digest = hashlib.blake2b(digest_size=32)
	with path.open("rb") as handle:
		for chunk in iter(lambda: handle.read(1_048_576), b""):
			digest.update(chunk)
	return digest.hexdigest()


def get_file_content_hash(path: Path) -> str:
	resolved = path.expanduser().resolve()
	cached = _run_file_hashes.get(resolved)
	if cached is not None:
		return cached
	content_hash = hash_file(resolved)
	_run_file_hashes[resolved] = content_hash
	return content_hash


def reset_run_file_hashes():
	_run_file_hashes.clear()


def reset_cache_connection():
	global _connection
	if _connection is not None:
		_connection.close()
		_connection = None


def _cache_key(kind: str, content_hash: str, variant: str) -> str:
	return f"{kind}:{content_hash}:{variant}"


def _get_connection() -> sqlite3.Connection:
	global _connection
	if _connection is None:
		db_path = cache_db_path()
		db_path.parent.mkdir(parents=True, exist_ok=True)
		_connection = sqlite3.connect(db_path, timeout=30.0)
		_connection.execute("PRAGMA journal_mode=WAL")
		_init_schema(_connection)
	return _connection


def _init_schema(connection: sqlite3.Connection):
	connection.execute(
		"""
		CREATE TABLE IF NOT EXISTS cache_meta (
			key TEXT PRIMARY KEY,
			value TEXT NOT NULL
		)
		"""
	)
	connection.execute(
		"""
		CREATE TABLE IF NOT EXISTS cache_entries (
			cache_key TEXT PRIMARY KEY,
			kind TEXT NOT NULL,
			content_hash TEXT NOT NULL,
			variant TEXT NOT NULL,
			payload BLOB NOT NULL,
			size_bytes INTEGER NOT NULL,
			created_at REAL NOT NULL,
			last_used REAL NOT NULL
		)
		"""
	)
	connection.execute("CREATE INDEX IF NOT EXISTS idx_cache_content ON cache_entries(content_hash, kind)")
	row = connection.execute("SELECT value FROM cache_meta WHERE key = 'schema_version'").fetchone()
	if row is None:
		connection.execute(
			"INSERT INTO cache_meta (key, value) VALUES ('schema_version', ?)",
			(str(_SCHEMA_VERSION),),
		)
	connection.commit()


def cache_get(kind: str, content_hash: str, variant: str) -> bytes | None:
	if cache_disabled():
		return None
	key = _cache_key(kind, content_hash, variant)
	connection = _get_connection()
	row = connection.execute(
		"SELECT payload FROM cache_entries WHERE cache_key = ?",
		(key,),
	).fetchone()
	if row is None:
		return None
	now = time.time()
	connection.execute("UPDATE cache_entries SET last_used = ? WHERE cache_key = ?", (now, key))
	connection.commit()
	return row[0]


def cache_put(kind: str, content_hash: str, variant: str, payload: bytes):
	if cache_disabled():
		return
	key = _cache_key(kind, content_hash, variant)
	now = time.time()
	size_bytes = len(payload)
	connection = _get_connection()
	connection.execute(
		"""
		INSERT INTO cache_entries (
			cache_key, kind, content_hash, variant, payload, size_bytes, created_at, last_used
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(cache_key) DO UPDATE SET
			payload = excluded.payload,
			size_bytes = excluded.size_bytes,
			last_used = excluded.last_used
		""",
		(key, kind, content_hash, variant, payload, size_bytes, now, now),
	)
	connection.commit()
	_evict_if_needed(connection)


def _evict_if_needed(connection: sqlite3.Connection):
	limit = cache_max_bytes()
	if limit is None:
		return
	total = connection.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM cache_entries").fetchone()
	if total is None or total[0] <= limit:
		return
	rows = connection.execute("SELECT cache_key, size_bytes FROM cache_entries ORDER BY last_used ASC").fetchall()
	current = total[0]
	for cache_key, size_bytes in rows:
		if current <= limit:
			break
		connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
		current -= size_bytes
	connection.commit()
