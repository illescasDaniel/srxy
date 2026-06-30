from __future__ import annotations

from pathlib import Path

import pytest

from srxy.cache import (
	CACHE_KIND_OCR_IMAGE,
	cache_db_path,
	cache_get,
	cache_key_path,
	cache_put,
	clear_results_cache,
	get_file_content_hash,
	hash_bytes,
	hash_file,
	main,
	reset_cache_connection,
	reset_run_file_hashes,
)


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_cache_connection()
	reset_run_file_hashes()


def test_given_same_bytes_when_hashing_then_produces_stable_digest():
	# given
	data = b"hello cache"

	# when / then
	assert hash_bytes(data) == hash_bytes(data)


def test_given_file_when_hashing_then_matches_streamed_bytes(tmp_path: Path):
	# given
	path = tmp_path / "sample.txt"
	path.write_bytes(b"file bytes")

	# when / then
	assert hash_file(path) == hash_bytes(b"file bytes")


def test_given_miss_then_put_when_getting_then_returns_payload():
	# given
	content_hash = hash_bytes(b"ocr payload")
	payload = b"recognized text"

	# when
	cache_put(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1", payload)
	cached = cache_get(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1")

	# then
	assert cached == payload


def test_given_cache_disabled_when_getting_then_returns_none(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DISABLE", "1")
	content_hash = hash_bytes(b"skip me")
	cache_put(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1", b"nope")

	# when / then
	assert cache_get(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1") is None


def test_given_same_path_twice_when_getting_file_hash_then_reuses_run_cache(tmp_path: Path):
	# given
	path = tmp_path / "photo.png"
	path.write_bytes(b"pixels")

	# when
	first = get_file_content_hash(path)
	second = get_file_content_hash(path)

	# then
	assert first == second


def test_given_cache_debug_when_getting_then_logs_to_stderr(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DEBUG", "1")
	content_hash = hash_bytes(b"debug-me")

	# when
	cache_put(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1", b"text")
	cache_get(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1")
	cache_get(CACHE_KIND_OCR_IMAGE, content_hash, "missing")

	# then
	err = capsys.readouterr().err
	assert "srxy cache PUT ocr_image" in err
	assert "srxy cache HIT ocr_image" in err
	assert "srxy cache MISS ocr_image" in err


def test_given_custom_cache_dir_when_resolving_db_path_then_uses_override(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "custom"))

	# when / then
	assert cache_db_path() == tmp_path / "custom" / "cache.db"


def test_given_cached_results_when_clearing_then_removes_cache_db(tmp_path: Path):
	# given
	content_hash = hash_bytes(b"clear me")
	cache_put(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1", b"payload")
	assert cache_db_path().exists()
	assert cache_key_path().exists()

	# when
	clear_results_cache()

	# then
	assert not cache_db_path().exists()
	assert not cache_key_path().exists()


def test_given_payload_when_putting_then_stores_encrypted_bytes(tmp_path: Path):
	# given
	content_hash = hash_bytes(b"encrypt me")
	payload = b"recognized text"

	# when
	cache_put(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1", payload)
	import sqlite3

	connection = sqlite3.connect(cache_db_path())
	row = connection.execute(
		"SELECT payload FROM cache_entries WHERE cache_key LIKE ?",
		(f"{CACHE_KIND_OCR_IMAGE}:{content_hash}:%",),
	).fetchone()
	connection.close()

	# then
	assert row is not None
	stored = row[0]
	assert stored.startswith(b"\x00srxy\x01")
	assert stored != payload


def test_given_modified_file_when_getting_hash_twice_then_recomputes(tmp_path: Path):
	# given
	path = tmp_path / "mutable.txt"
	path.write_bytes(b"version-one")
	first = get_file_content_hash(path)

	# when
	path.write_bytes(b"version-two-with-different-size")
	second = get_file_content_hash(path)

	# then
	assert first != second


def test_given_cache_from_two_threads_when_getting_then_returns_payload():
	# given
	import threading

	content_hash = hash_bytes(b"thread-safe")
	cache_put(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1", b"thread payload")
	errors: list[Exception] = []
	results: list[bytes | None] = []

	def worker():
		try:
			results.append(cache_get(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1"))
		except Exception as error:
			errors.append(error)

	threads = [threading.Thread(target=worker) for _ in range(4)]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join()

	# then
	assert not errors
	assert results == [b"thread payload"] * 4


def test_given_missing_cache_when_clearing_then_is_noop(tmp_path: Path):
	# given
	db_path = cache_db_path()
	if db_path.exists():
		db_path.unlink()

	# when / then
	clear_results_cache()
	assert not db_path.exists()


def test_given_clear_cli_when_invoked_then_removes_cache_db(tmp_path: Path):
	# given
	content_hash = hash_bytes(b"cli clear")
	cache_put(CACHE_KIND_OCR_IMAGE, content_hash, "tesseract-v1", b"payload")

	# when
	exit_code = main(["clear"])

	# then
	assert exit_code == 0
	assert not cache_db_path().exists()
