from __future__ import annotations

from pathlib import Path

import pytest

from srxy.cache import (
	CACHE_KIND_OCR_IMAGE,
	cache_db_path,
	cache_get,
	cache_put,
	get_file_content_hash,
	hash_bytes,
	hash_file,
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


def test_given_custom_cache_dir_when_resolving_db_path_then_uses_override(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "custom"))

	# when / then
	assert cache_db_path() == tmp_path / "custom" / "cache.db"
