from __future__ import annotations

import hashlib
import io
import tempfile
import urllib.request
from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.download import ALLOW_UNVERIFIED_ENV, download_file, download_to_temp


pytestmark = pytest.mark.unit

PAYLOAD = b"srxy installer artifact payload"
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://example.invalid/artifact.bin"


class _FakeResponse(io.BytesIO):
	def __init__(self, payload: bytes):
		super().__init__(payload)
		self.headers: dict[str, str] = {"Content-Length": str(len(payload))}


def _serve(monkeypatch: pytest.MonkeyPatch, payload: bytes = PAYLOAD):
	"""Replace urlopen with an in-memory body served for the pinned test URL."""

	def fake_urlopen(request: urllib.request.Request, timeout: float = 0.0) -> _FakeResponse:
		assert request.full_url == URL
		assert timeout > 0
		return _FakeResponse(payload)

	monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def _refuse_network(monkeypatch: pytest.MonkeyPatch):
	"""Fail loudly if a rejected download still tries to open a connection."""

	def fail_urlopen(*_args: object, **_kwargs: object) -> _FakeResponse:
		raise AssertionError("download must be rejected before opening a connection")

	monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)


def _part_of(destination: Path) -> Path:
	return destination.with_name(destination.name + ".part")


def test_given_http_url_when_downloading_then_rejects_before_connecting(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	_refuse_network(monkeypatch)
	destination = tmp_path / "artifact.bin"

	# when
	with pytest.raises(RuntimeError, match="non-https"):
		download_file("http://example.invalid/artifact.bin", destination, sha256=PAYLOAD_SHA256)

	# then
	assert not destination.exists()
	assert not _part_of(destination).exists()


def test_given_missing_sha256_when_downloading_then_refuses_unverified_download(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.delenv(ALLOW_UNVERIFIED_ENV, raising=False)
	_refuse_network(monkeypatch)
	destination = tmp_path / "artifact.bin"

	# when
	with pytest.raises(RuntimeError, match=ALLOW_UNVERIFIED_ENV):
		download_file(URL, destination, sha256="")

	# then
	assert not destination.exists()
	assert not _part_of(destination).exists()


def test_given_allow_unverified_env_when_downloading_without_sha256_then_writes_file(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv(ALLOW_UNVERIFIED_ENV, "1")
	_serve(monkeypatch)
	destination = tmp_path / "nested" / "artifact.bin"

	# when
	result = download_file(URL, destination, sha256="")

	# then
	assert result == destination
	assert destination.read_bytes() == PAYLOAD
	assert not _part_of(destination).exists()


def test_given_wrong_sha256_when_downloading_then_fails_without_leaving_files(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	_serve(monkeypatch)
	destination = tmp_path / "artifact.bin"

	# when
	with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
		download_file(URL, destination, sha256="0" * 64)

	# then
	assert not destination.exists()
	assert not _part_of(destination).exists()


def test_given_existing_destination_when_download_digest_mismatches_then_keeps_previous_file(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	_serve(monkeypatch)
	destination = tmp_path / "artifact.bin"
	destination.write_bytes(b"previous good copy")

	# when
	with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
		download_file(URL, destination, sha256="0" * 64)

	# then
	assert destination.read_bytes() == b"previous good copy"
	assert not _part_of(destination).exists()


def test_given_correct_sha256_when_downloading_then_writes_destination_and_reports_progress(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	_serve(monkeypatch)
	destination = tmp_path / "artifact.bin"
	events: list[tuple[int, int, str]] = []

	# when
	result = download_file(
		URL,
		destination,
		sha256=PAYLOAD_SHA256.upper(),
		label="artifact 1.0",
		progress=lambda downloaded, total, label: events.append((downloaded, total, label)),
	)

	# then
	assert result == destination
	assert destination.read_bytes() == PAYLOAD
	assert not _part_of(destination).exists()
	assert events[-1] == (len(PAYLOAD), len(PAYLOAD), "artifact 1.0")


def test_given_correct_sha256_when_downloading_to_temp_then_returns_verified_file(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	_serve(monkeypatch)
	monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

	# when
	path = download_to_temp(URL, suffix=".bin", sha256=PAYLOAD_SHA256)

	# then
	assert path.parent == tmp_path
	assert path.read_bytes() == PAYLOAD
	assert not _part_of(path).exists()


def test_given_missing_sha256_when_downloading_to_temp_then_leaves_no_temp_file(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.delenv(ALLOW_UNVERIFIED_ENV, raising=False)
	_refuse_network(monkeypatch)
	monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

	# when
	with pytest.raises(RuntimeError, match=ALLOW_UNVERIFIED_ENV):
		download_to_temp(URL, suffix=".bin", sha256="")

	# then
	assert list(tmp_path.iterdir()) == []
