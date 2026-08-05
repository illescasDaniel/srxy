"""Pinned upstream download catalog for desktop installer dependencies."""

from __future__ import annotations

import platform
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


@dataclass(frozen=True, slots=True)
class BrewBottle:
	"""Pinned Homebrew core bottle blob (immutable ghcr.io digest URL)."""

	formula: str
	version: str
	url: str
	sha256: str


# Homebrew's public anonymous GHCR token (not a secret). Required to fetch core bottle blobs.
GHCR_BOTTLE_HEADERS: dict[str, str] = {
	"Authorization": "Bearer QQ==",
	"Accept": "application/vnd.oci.image.layer.v1.tar+gzip",
}


def _brew_bottle(formula: str, version: str, digest: str) -> BrewBottle:
	return BrewBottle(
		formula=formula,
		version=version,
		url=f"https://ghcr.io/v2/homebrew/core/{formula}/blobs/sha256:{digest}",
		sha256=digest,
	)


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


# Homebrew core arm64_sonoma bottles. Digests are the bottle file SHA-256 (also the ghcr blob id).
# Source of truth: https://formulae.brew.sh/api/formula/<name>.json → bottle.stable.files.arm64_sonoma
DARWIN_ARM64_TESSERACT_BOTTLES: tuple[BrewBottle, ...] = (
	_brew_bottle("tesseract", "5.5.3", "5a992bfcbb16e0dd15250c490bb0df82545eb9113713b3bfea3ca273a36fe649"),
	_brew_bottle("leptonica", "1.87.0", "bc58db017510f010f5feccc1e88aaaf3ca118dc6750ad9ecef6cbb47e0358539"),
	_brew_bottle("libarchive", "3.8.9", "4561e7a6d54788627a8e50f188a5f8bddcba31ad1676423b84a8723282e77d2e"),
	_brew_bottle("giflib", "6.1.3", "513c620b8bcf0f74370b4852fa823f1e29761b843540abfb6b9fa9cd9517994b"),
	_brew_bottle("jpeg-turbo", "3.2.0", "0d248d272a2e9d4f3442ce8d82c2df322079e77a76011cf75cb18d7114e78655"),
	_brew_bottle("libpng", "1.6.58", "fd6cbd5d7a231b83e359fd96231bb3dd668124ab5c2009697dee906ace98fadd"),
	_brew_bottle("libtiff", "4.7.2", "3783a59d14d00405ee96a9cbf5bba49a9c764c62b67274e642e71a0f65c9fb6e"),
	_brew_bottle("openjpeg", "2.5.4", "0eff9d5aae88cd27eaaedb4a4f56804ae14c4ed9df1c856846ff81ebc3dcb4c2"),
	_brew_bottle("webp", "1.6.0", "2c0172632efa4d17103aad0d82dd27addce7db290b5cf52cd9afcbff3c39a497"),
	_brew_bottle("libb2", "0.98.1", "52cef2730b3520e99f75f1478f2b953dc46e362a8dbf90f2c6a9028b47bbb8bd"),
	_brew_bottle("lz4", "1.10.0", "6590245dc4a919c46afa16366914cd4b5c0c4a8f4fb35a4f6ab89053f289ae5d"),
	_brew_bottle("xz", "5.8.3", "0a6e40dbeea3358a1277f347ef9b892070096a79a81cda90edfedbfe721c4ba3"),
	_brew_bottle("zstd", "1.5.7", "35b5150b27512a94ebaee7b4399aaa8adf42d247e6968319e4aeac3c05365281"),
)


DARWIN_ARM64_CATALOG: dict[str, DownloadArtifact] = {
	"uv": DownloadArtifact(
		name="uv",
		version="0.12.1",
		url="https://github.com/astral-sh/uv/releases/download/0.12.1/uv-aarch64-apple-darwin.tar.gz",
		sha256="77d2906988e8074fd43f2f329ec452ebbf9b0c257ba1c66451c71de70a6baf42",
		kind="archive",
		notes="Astral uv standalone (Apple Silicon, Apache-2.0 / MIT).",
	),
	# Assembled at install time from pinned Homebrew core arm64_sonoma bottles (ghcr.io).
	"tesseract": DownloadArtifact(
		name="tesseract",
		version=DARWIN_ARM64_TESSERACT_BOTTLES[0].version,
		url=DARWIN_ARM64_TESSERACT_BOTTLES[0].url,
		sha256=DARWIN_ARM64_TESSERACT_BOTTLES[0].sha256,
		kind="brew_bottles",
		notes="Homebrew core tesseract + runtime deps (arm64_sonoma bottles via ghcr.io).",
	),
	"tessdata_eng": DownloadArtifact(
		name="tessdata_eng",
		version="4.1.0",
		url=(
			"https://raw.githubusercontent.com/tesseract-ocr/tessdata/"
			"4767ea922bcc460e70b87b1d303ebdfed0897da8/eng.traineddata"
		),
		sha256="daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047",
		kind="file",
		notes="English traineddata for Tesseract, tessdata 4.1.0 (Apache-2.0).",
	),
	# Static arm64 ffmpeg from martin-riedl immutable snapshot URL (zip of a single binary).
	"ffmpeg": DownloadArtifact(
		name="ffmpeg",
		version="8.1.2",
		url="https://ffmpeg.martin-riedl.de/download/macos/arm64/1783011502_8.1.2/ffmpeg.zip",
		sha256="ef1aa60006c7b77ce170c1608c08d8e4ba1c30c5746f2ac986ded932d0ac2c3c",
		kind="zip",
		notes="Static FFmpeg 8.1.2 for Apple Silicon (martin-riedl builds).",
	),
}

DARWIN_X86_64_CATALOG: dict[str, DownloadArtifact] = {
	"uv": DownloadArtifact(
		name="uv",
		version="0.12.1",
		url="https://github.com/astral-sh/uv/releases/download/0.12.1/uv-x86_64-apple-darwin.tar.gz",
		sha256="69d9f9a00337f25a50dcb13882052da08b8469bac11091c98c5694c3c6721467",
		kind="archive",
		notes="Astral uv standalone (Intel macOS, Apache-2.0 / MIT).",
	),
}


WIN_X86_64_CATALOG: dict[str, DownloadArtifact] = {
	"uv": DownloadArtifact(
		name="uv",
		version="0.12.1",
		url="https://github.com/astral-sh/uv/releases/download/0.12.1/uv-x86_64-pc-windows-msvc.zip",
		sha256="8fcb0cb46e1229065e344758980924e569bef5882ef45f46fada8fb24e06b74a",
		kind="zip",
		notes="Astral uv standalone (Windows x86_64, Apache-2.0 / MIT).",
	),
	# UB-Mannheim NSIS setup; extracted (not executed) into the prefix vendor tree — avoids UAC.
	"tesseract": DownloadArtifact(
		name="tesseract",
		version="5.4.0.20240606",
		url=(
			"https://github.com/UB-Mannheim/tesseract/releases/download/"
			"v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
		),
		sha256="c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9",
		kind="nsis_installer",
		notes="UB-Mannheim Tesseract OCR Windows x64 NSIS setup (Apache-2.0); extracted without elevation.",
	),
	# Install-time helpers only (not shipped in the offline EXE). Used to unpack the NSIS setup.
	"7zr": DownloadArtifact(
		name="7zr",
		version="24.09",
		url="https://github.com/ip7z/7zip/releases/download/24.09/7zr.exe",
		sha256="d2c0045523cf053a6b43f9315e9672fc2535f06aeadd4ffa53c729cd8b2b6dfe",
		kind="binary",
		notes="7-Zip reduced console (public domain) for unpacking the full 7-Zip SFX.",
	),
	"7zip": DownloadArtifact(
		name="7zip",
		version="24.09",
		url="https://github.com/ip7z/7zip/releases/download/24.09/7z2409-x64.exe",
		sha256="bdd1a33de78618d16ee4ce148b849932c05d0015491c34887846d431d29f308e",
		kind="sfx",
		notes="7-Zip 24.09 Windows x64 SFX (LGPL) providing 7z.exe+7z.dll for NSIS extraction.",
	),
	"tessdata_eng": DownloadArtifact(
		name="tessdata_eng",
		version="4.1.0",
		url=(
			"https://raw.githubusercontent.com/tesseract-ocr/tessdata/"
			"4767ea922bcc460e70b87b1d303ebdfed0897da8/eng.traineddata"
		),
		sha256="daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047",
		kind="file",
		notes="English traineddata for Tesseract, tessdata 4.1.0 (Apache-2.0).",
	),
	"ffmpeg": DownloadArtifact(
		name="ffmpeg",
		version="n8.1.2-34-g9b6c8969e0",
		url=(
			"https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-08-01-13-21/"
			"ffmpeg-n8.1.2-34-g9b6c8969e0-win64-lgpl-shared-8.1.zip"
		),
		sha256="3bba81dcfd017a6ea1627905549769913948831ef10f3e7df7541f736067bff8",
		kind="zip",
		notes="FFmpeg 8.1 Windows x86_64 LGPL shared build (BtbN autobuild-2026-08-01-13-21).",
	),
}


def _normalize_machine(value: str) -> str:
	machine = value.strip().lower()
	aliases = {
		"amd64": "x86_64",
		"x64": "x86_64",
		"x86-64": "x86_64",
		"arm64e": "arm64",
		"aarch64": "arm64",
	}
	return aliases.get(machine, machine)


def platform_catalog() -> dict[str, DownloadArtifact]:
	system = platform.system().lower()
	machine = _normalize_machine(platform.machine())
	if system == "linux" and machine == "x86_64":
		return LINUX_X86_64_CATALOG
	if system == "darwin" and machine == "arm64":
		return DARWIN_ARM64_CATALOG
	if system == "darwin" and machine == "x86_64":
		return DARWIN_X86_64_CATALOG
	if system == "windows" and machine == "x86_64":
		return WIN_X86_64_CATALOG
	return LINUX_X86_64_CATALOG


def vendor_downloads_supported() -> bool:
	"""True when this host can auto-download tesseract/ffmpeg from the pinned catalog."""
	system = platform.system().lower()
	machine = _normalize_machine(platform.machine())
	if system == "linux" and machine == "x86_64":
		return True
	if system == "darwin" and machine == "arm64":
		return True
	if system == "windows" and machine == "x86_64":
		return True
	return False


def artifact(name: str) -> DownloadArtifact:
	catalog = platform_catalog()
	try:
		return catalog[name]
	except KeyError as exc:
		raise KeyError(f"unknown installer artifact for this platform: {name}") from exc


__all__ = [
	"BrewBottle",
	"DARWIN_ARM64_CATALOG",
	"DARWIN_ARM64_TESSERACT_BOTTLES",
	"DARWIN_X86_64_CATALOG",
	"DownloadArtifact",
	"GHCR_BOTTLE_HEADERS",
	"LINUX_X86_64_CATALOG",
	"WIN_X86_64_CATALOG",
	"artifact",
	"platform_catalog",
	"vendor_downloads_supported",
]
