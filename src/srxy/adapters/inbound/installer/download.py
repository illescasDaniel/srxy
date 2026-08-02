"""Download helpers with optional SHA-256 verification."""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path


ProgressCallback = Callable[[int, int, str], None]


def _report(progress: ProgressCallback | None, downloaded: int, total: int, label: str):
	if progress is not None:
		progress(downloaded, total, label)


def download_file(
	url: str,
	destination: Path,
	*,
	sha256: str = "",
	label: str = "",
	progress: ProgressCallback | None = None,
) -> Path:
	destination.parent.mkdir(parents=True, exist_ok=True)
	display = label or destination.name
	if not url.startswith(("https://", "http://")):
		raise RuntimeError(f"refusing non-http(s) download URL: {url}")
	request = urllib.request.Request(url, headers={"User-Agent": "srxy-installer"})  # noqa: S310
	try:
		with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
			total = int(response.headers.get("Content-Length") or 0)
			hasher = hashlib.sha256()
			downloaded = 0
			with destination.open("wb") as handle:
				while True:
					chunk = response.read(1024 * 256)
					if not chunk:
						break
					handle.write(chunk)
					hasher.update(chunk)
					downloaded += len(chunk)
					_report(progress, downloaded, total, display)
	except urllib.error.URLError as exc:
		raise RuntimeError(f"failed to download {url}: {exc}") from exc

	digest = hasher.hexdigest()
	expected = sha256.strip().lower()
	if expected and digest != expected:
		destination.unlink(missing_ok=True)
		raise RuntimeError(f"SHA-256 mismatch for {display}: got {digest}, expected {expected}")
	_report(progress, downloaded, total or downloaded, display)
	return destination


def extract_tar_archive(archive: Path, destination: Path) -> Path:
	destination.mkdir(parents=True, exist_ok=True)
	with tarfile.open(archive, mode="r:*") as handle:
		handle.extractall(destination, filter="data")  # type: ignore[call-arg]
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
) -> Path:
	handle = tempfile.NamedTemporaryFile(prefix="srxy-dl-", suffix=suffix, delete=False)
	handle.close()
	path = Path(handle.name)
	try:
		return download_file(url, path, sha256=sha256, label=label, progress=progress)
	except Exception:
		path.unlink(missing_ok=True)
		raise


__all__ = [
	"ProgressCallback",
	"download_file",
	"download_to_temp",
	"extract_tar_archive",
	"move_tree",
]
