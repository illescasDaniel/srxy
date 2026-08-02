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


# Every URL must be https and immutable: a release tag asset or a raw commit URL,
# never a floating "latest"/"main" ref, so the pinned sha256 stays valid.
# packaging/linux-appimage/refresh_checksums.sh downloads each URL and rewrites the
# sha256 fields below. An empty sha256 is refused at download time unless
# SRXY_INSTALLER_ALLOW_UNVERIFIED=1 is set (dev only).
LINUX_X86_64_CATALOG: dict[str, DownloadArtifact] = {
	"uv": DownloadArtifact(
		name="uv",
		version="0.12.1",
		url="https://github.com/astral-sh/uv/releases/download/0.12.1/uv-x86_64-unknown-linux-gnu.tar.gz",
		sha256="90b2f223fb69d19db49e117da601f64978593417988530aa733d456141b4bcbb",
		kind="archive",
		notes="Astral uv standalone (Apache-2.0 / MIT).",
	),
	"tesseract": DownloadArtifact(
		name="tesseract",
		version="5.5.3",
		url="https://github.com/DanielMYT/tesseract-static/releases/download/tesseract-5.5.3/tesseract.x86_64",
		sha256="1ee53ab818ba128de01ba631e09911c5b6ed6cb63c741323097f209b797f68b0",
		kind="binary",
		notes="Statically linked Tesseract (Apache-2.0).",
	),
	"tessdata_eng": DownloadArtifact(
		name="tessdata_eng",
		version="4.1.0",
		# Commit 4767ea9 is the tesseract-ocr/tessdata 4.1.0 tag; raw commit URLs never move.
		url=(
			"https://raw.githubusercontent.com/tesseract-ocr/tessdata/"
			"4767ea922bcc460e70b87b1d303ebdfed0897da8/eng.traineddata"
		),
		sha256="daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047",
		kind="file",
		notes="English traineddata for Tesseract, tessdata 4.1.0 (Apache-2.0).",
	),
	# BtbN LGPL shared build — prefer over GPL-only static archives when possible.
	# Autobuild tags are immutable snapshots; the mutable "latest" tag is not usable here
	# because its assets are replaced on every upstream build.
	"ffmpeg": DownloadArtifact(
		name="ffmpeg",
		version="n8.1.2-34-g9b6c8969e0",
		url=(
			"https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-08-01-13-21/"
			"ffmpeg-n8.1.2-34-g9b6c8969e0-linux64-lgpl-shared-8.1.tar.xz"
		),
		sha256="e9144cae41096aba50d7c6caba0d15822ad04f9f3a97f394cecd7bb93eae68b8",
		kind="archive",
		notes="FFmpeg 8.1 Linux x86_64 LGPL shared build (BtbN autobuild-2026-08-01-13-21).",
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
