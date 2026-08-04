"""Download helpers with HTTPS-only transport and SHA-256 verification."""

from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path


ProgressCallback = Callable[[int, int, str], None]

# Opt-out for local development against artifacts whose checksum is not pinned yet.
ALLOW_UNVERIFIED_ENV = "SRXY_INSTALLER_ALLOW_UNVERIFIED"

_CHUNK_SIZE = 1024 * 256
_TIMEOUT_SECONDS = 120


def _report(progress: ProgressCallback | None, downloaded: int, total: int, label: str):
	if progress is not None:
		progress(downloaded, total, label)


def _partial_path(destination: Path) -> Path:
	return destination.with_name(destination.name + ".part")


def _check_source(url: str, expected_digest: str, display: str):
	if not url.startswith("https://"):
		raise RuntimeError(f"refusing non-https download URL: {url}")
	if expected_digest:
		return
	if os.environ.get(ALLOW_UNVERIFIED_ENV, "").strip() == "1":
		return
	raise RuntimeError(f"missing SHA-256 for {display}; set {ALLOW_UNVERIFIED_ENV}=1 to allow unverified downloads")


def _stream_to_file(
	url: str,
	target: Path,
	*,
	display: str,
	progress: ProgressCallback | None,
	headers: Mapping[str, str] | None,
) -> str:
	"""Stream ``url`` into ``target`` and return the hex SHA-256 of the bytes written."""
	request_headers = {"User-Agent": "srxy-installer"}
	if headers:
		request_headers.update(headers)
	request = urllib.request.Request(url, headers=request_headers)  # noqa: S310
	hasher = hashlib.sha256()
	downloaded = 0
	total = 0
	try:
		with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
			total = int(response.headers.get("Content-Length") or 0)
			with target.open("wb") as handle:
				while True:
					chunk = response.read(_CHUNK_SIZE)
					if not chunk:
						break
					handle.write(chunk)
					hasher.update(chunk)
					downloaded += len(chunk)
					_report(progress, downloaded, total, display)
	except urllib.error.URLError as exc:
		raise RuntimeError(f"failed to download {url}: {exc}") from exc
	_report(progress, downloaded, total or downloaded, display)
	return hasher.hexdigest()


def download_file(
	url: str,
	destination: Path,
	*,
	sha256: str = "",
	label: str = "",
	progress: ProgressCallback | None = None,
	headers: Mapping[str, str] | None = None,
) -> Path:
	display = label or destination.name
	expected = sha256.strip().lower()
	_check_source(url, expected, display)

	destination.parent.mkdir(parents=True, exist_ok=True)
	partial = _partial_path(destination)
	partial.unlink(missing_ok=True)
	try:
		digest = _stream_to_file(url, partial, display=display, progress=progress, headers=headers)
		if expected and digest != expected:
			raise RuntimeError(f"SHA-256 mismatch for {display}: got {digest}, expected {expected}")
		os.replace(partial, destination)
	except BaseException:
		partial.unlink(missing_ok=True)
		raise
	return destination


def extract_tar_archive(archive: Path, destination: Path) -> Path:
	destination.mkdir(parents=True, exist_ok=True)
	with tarfile.open(archive, mode="r:*") as handle:
		handle.extractall(destination, filter="data")  # type: ignore[call-arg]
	return destination


def extract_zip_archive(archive: Path, destination: Path) -> Path:
	destination.mkdir(parents=True, exist_ok=True)
	dest_root = destination.resolve()
	with zipfile.ZipFile(archive) as handle:
		for info in handle.infolist():
			member_path = Path(info.filename)
			if member_path.is_absolute() or ".." in member_path.parts:
				raise RuntimeError(f"refusing unsafe zip member path: {info.filename}")
			target = (destination / member_path).resolve()
			if not target.is_relative_to(dest_root):
				raise RuntimeError(f"refusing zip member outside destination: {info.filename}")
			handle.extract(info, destination)
	return destination


def move_tree(source: Path, destination: Path):
	if destination.exists():
		shutil.rmtree(destination)
	destination.parent.mkdir(parents=True, exist_ok=True)
	shutil.move(str(source), str(destination))


def download_to_temp(
	url: str,
	*,
	suffix: str,
	sha256: str = "",
	label: str = "",
	progress: ProgressCallback | None = None,
	headers: Mapping[str, str] | None = None,
) -> Path:
	handle = tempfile.NamedTemporaryFile(prefix="srxy-dl-", suffix=suffix, delete=False)
	handle.close()
	path = Path(handle.name)
	try:
		return download_file(url, path, sha256=sha256, label=label, progress=progress, headers=headers)
	except BaseException:
		path.unlink(missing_ok=True)
		raise


__all__ = [
	"ALLOW_UNVERIFIED_ENV",
	"ProgressCallback",
	"download_file",
	"download_to_temp",
	"extract_tar_archive",
	"extract_zip_archive",
	"move_tree",
]
