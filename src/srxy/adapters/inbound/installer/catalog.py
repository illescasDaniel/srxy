"""Pinned upstream download catalog for the desktop installer (Linux x86_64)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
	name: str
	version: str
	url: str
	sha256: str
	# Relative path under prefix/vendor/<name>/ after extraction, or binary name.
	kind: str
	notes: str = ""


# Checksums are verified when non-empty. Empty sha256 skips verify (dev only);
# packaging/linux-appimage/refresh_checksums.sh fills them for releases.
LINUX_X86_64_CATALOG: dict[str, DownloadArtifact] = {
	"uv": DownloadArtifact(
		name="uv",
		version="0.12.1",
		url="https://github.com/astral-sh/uv/releases/download/0.12.1/uv-x86_64-unknown-linux-gnu.tar.gz",
		sha256="",
		kind="archive",
		notes="Astral uv standalone (Apache-2.0 / MIT).",
	),
	"tesseract": DownloadArtifact(
		name="tesseract",
		version="5.5.3",
		url="https://github.com/DanielMYT/tesseract-static/releases/download/tesseract-5.5.3/tesseract.x86_64",
		sha256="",
		kind="binary",
		notes="Statically linked Tesseract (Apache-2.0).",
	),
	"tessdata_eng": DownloadArtifact(
		name="tessdata_eng",
		version="main",
		url="https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata",
		sha256="",
		kind="file",
		notes="English traineddata for Tesseract (Apache-2.0).",
	),
	# BtbN LGPL shared build — prefer over GPL-only static archives when possible.
	"ffmpeg": DownloadArtifact(
		name="ffmpeg",
		version="latest-lgpl",
		url=(
			"https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
			"ffmpeg-master-latest-linux64-lgpl-shared.tar.xz"
		),
		sha256="",
		kind="archive",
		notes="FFmpeg Linux x86_64 LGPL shared build (BtbN).",
	),
}


def artifact(name: str) -> DownloadArtifact:
	try:
		return LINUX_X86_64_CATALOG[name]
	except KeyError as exc:
		raise KeyError(f"unknown installer artifact: {name}") from exc


__all__ = [
	"DownloadArtifact",
	"LINUX_X86_64_CATALOG",
	"artifact",
]
