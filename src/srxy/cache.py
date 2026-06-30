from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


CACHE_KIND_OCR_IMAGE = "ocr_image"
CACHE_KIND_OCR_PDF_BLOB = "ocr_pdf_blob"
CACHE_KIND_CLIP_EMBED = "clip_embed"
CACHE_KIND_TRANSCRIPT = "transcript"
CACHE_KIND_SEMANTIC_EMBED = "semantic_embed"
CACHE_KIND_DOCUMENT_TEXT = "document_text"

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})
_SCHEMA_VERSION = 2
_ENCRYPTED_PREFIX = b"\x00srxy\x01"

_connection: sqlite3.Connection | None = None
_connection_lock = threading.RLock()
_run_file_hashes: dict[Path, tuple[str, int, int]] = {}
_fernet: Fernet | None = None


def cache_disabled() -> bool:
	value = os.environ.get("SRXY_CACHE_DISABLE", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def cache_debug_enabled() -> bool:
	value = os.environ.get("SRXY_CACHE_DEBUG", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def _log_cache_event(event: str, kind: str, content_hash: str, variant: str):
	if not cache_debug_enabled():
		return
	print(f"srxy cache {event} {kind} hash={content_hash[:12]} variant={variant}", file=sys.stderr)


def cache_db_path() -> Path:
	raw = os.environ.get("SRXY_CACHE_DIR", "").strip()
	if raw:
		return Path(raw).expanduser() / "cache.db"
	return Path.home() / ".cache" / "srxy" / "cache.db"


def cache_key_path() -> Path:
	return cache_db_path().with_name(".cache_key")


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
	stat = resolved.stat()
	fingerprint = (stat.st_mtime_ns, stat.st_size)
	cached = _run_file_hashes.get(resolved)
	if cached is not None and cached[1:] == fingerprint:
		return cached[0]
	content_hash = hash_file(resolved)
	_run_file_hashes[resolved] = (content_hash, stat.st_mtime_ns, stat.st_size)
	return content_hash


def reset_run_file_hashes():
	_run_file_hashes.clear()


def reset_cache_connection():
	global _connection, _fernet
	with _connection_lock:
		if _connection is not None:
			_connection.close()
			_connection = None
		_fernet = None


def _cache_key(kind: str, content_hash: str, variant: str) -> str:
	return f"{kind}:{content_hash}:{variant}"


def _load_or_create_fernet() -> Fernet:
	global _fernet
	if _fernet is not None:
		return _fernet

	env_key = os.environ.get("SRXY_CACHE_KEY", "").strip()
	if env_key:
		_fernet = Fernet(env_key.encode("ascii"))
		return _fernet

	key_path = cache_key_path()
	if key_path.is_file():
		raw = key_path.read_bytes().strip()
		_fernet = Fernet(raw)
		return _fernet

	key_path.parent.mkdir(parents=True, exist_ok=True)
	key = Fernet.generate_key()
	key_path.write_bytes(key)
	try:
		os.chmod(key_path, 0o600)
	except OSError:
		pass
	_fernet = Fernet(key)
	return _fernet


def _encrypt_payload(payload: bytes) -> bytes:
	return _ENCRYPTED_PREFIX + _load_or_create_fernet().encrypt(payload)


def _decrypt_payload(stored: bytes) -> bytes | None:
	if not stored.startswith(_ENCRYPTED_PREFIX):
		return None
	try:
		return _load_or_create_fernet().decrypt(stored[len(_ENCRYPTED_PREFIX) :])
	except InvalidToken:
		return None


def _get_connection() -> sqlite3.Connection:
	global _connection
	with _connection_lock:
		if _connection is None:
			db_path = cache_db_path()
			db_path.parent.mkdir(parents=True, exist_ok=True)
			_connection = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
			_connection.execute("PRAGMA journal_mode=WAL")
			_init_schema(_connection)
		return _connection


def _migrate_schema(connection: sqlite3.Connection):
	row = connection.execute("SELECT value FROM cache_meta WHERE key = 'schema_version'").fetchone()
	current_version = int(row[0]) if row is not None else 1
	if current_version >= _SCHEMA_VERSION:
		return
	connection.execute("DELETE FROM cache_entries")
	connection.execute(
		"INSERT INTO cache_meta (key, value) VALUES ('schema_version', ?) "
		"ON CONFLICT(key) DO UPDATE SET value = excluded.value",
		(str(_SCHEMA_VERSION),),
	)
	connection.commit()


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
	else:
		_migrate_schema(connection)


def cache_get(kind: str, content_hash: str, variant: str) -> bytes | None:
	if cache_disabled():
		return None
	key = _cache_key(kind, content_hash, variant)
	with _connection_lock:
		connection = _get_connection()
		row = connection.execute(
			"SELECT payload FROM cache_entries WHERE cache_key = ?",
			(key,),
		).fetchone()
		if row is None:
			_log_cache_event("MISS", kind, content_hash, variant)
			return None
		payload = _decrypt_payload(row[0])
		if payload is None:
			_log_cache_event("MISS", kind, content_hash, variant)
			connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
			connection.commit()
			return None
		_log_cache_event("HIT", kind, content_hash, variant)
		now = time.time()
		connection.execute("UPDATE cache_entries SET last_used = ? WHERE cache_key = ?", (now, key))
		connection.commit()
		return payload


def cache_put(kind: str, content_hash: str, variant: str, payload: bytes):
	if cache_disabled():
		return
	_log_cache_event("PUT", kind, content_hash, variant)
	key = _cache_key(kind, content_hash, variant)
	now = time.time()
	encrypted = _encrypt_payload(payload)
	size_bytes = len(encrypted)
	with _connection_lock:
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
			(key, kind, content_hash, variant, encrypted, size_bytes, now, now),
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


def clear_results_cache():
	db_path = cache_db_path()
	key_path = cache_key_path()
	reset_cache_connection()
	removed = False
	if db_path.exists():
		db_path.unlink()
		removed = True
	if key_path.exists():
		key_path.unlink()
		removed = True
	if not removed:
		print(f"Results cache is not present at {db_path}", file=sys.stderr)
		return
	print(f"Removed results cache at {db_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
	import argparse

	if argv is None:
		argv = sys.argv[1:]

	parser = argparse.ArgumentParser(description="Manage srxy results cache (OCR, transcripts, embeddings).")
	subparsers = parser.add_subparsers(dest="command", required=True)
	subparsers.add_parser("clear", help="Remove cache.db and encryption key")
	args = parser.parse_args(argv)

	if args.command == "clear":
		clear_results_cache()
	return 0


if __name__ == "__main__":
	sys.exit(main())
