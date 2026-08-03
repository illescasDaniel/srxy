"""Resolve install-prefix paths when SRXY_HOME is set (desktop installer layout).

PyPI / uv-tool installs leave SRXY_HOME unset and keep ~/.cache/srxy defaults.
"""

from __future__ import annotations

import os
from pathlib import Path


MANIFEST_NAME = ".srxy-manifest.json"
DEFAULT_INSTALL_DIRNAME = "srxy"


def srxy_home() -> Path | None:
	raw = os.environ.get("SRXY_HOME", "").strip()
	if not raw:
		return None
	return Path(raw).expanduser().resolve()


def default_install_prefix() -> Path:
	return Path.home() / "Applications" / DEFAULT_INSTALL_DIRNAME


def default_cache_root() -> Path:
	override = os.environ.get("SRXY_CACHE_DIR", "").strip()
	if override:
		return Path(override).expanduser()
	home = srxy_home()
	if home is not None:
		return home / "cache"
	return Path.home() / ".cache" / "srxy"


def models_root() -> Path:
	home = srxy_home()
	if home is not None:
		return home / "models"
	return default_cache_root()


def vendor_root() -> Path | None:
	home = srxy_home()
	if home is None:
		return None
	return home / "vendor"


def vendor_tesseract_dir() -> Path | None:
	root = vendor_root()
	if root is None:
		return None
	return root / "tesseract"


def vendor_ffmpeg_dir() -> Path | None:
	root = vendor_root()
	if root is None:
		return None
	return root / "ffmpeg"


def resolve_tesseract_binary() -> Path | None:
	override = os.environ.get("SRXY_TESSERACT_PATH", "").strip()
	if override:
		path = Path(override).expanduser()
		return path if path.is_file() else None
	vendor = vendor_tesseract_dir()
	if vendor is not None:
		candidate = vendor / "bin" / "tesseract"
		if candidate.is_file():
			return candidate
		legacy = vendor / "tesseract"
		if legacy.is_file():
			return legacy
	return None


def resolve_tessdata_prefix() -> Path | None:
	override = os.environ.get("TESSDATA_PREFIX", "").strip()
	if override:
		return Path(override).expanduser()
	vendor = vendor_tesseract_dir()
	if vendor is None:
		return None
	for candidate in (vendor / "tessdata", vendor / "share" / "tessdata"):
		if candidate.is_dir():
			return candidate
	return None


def resolve_ffmpeg_binary() -> Path | None:
	override = os.environ.get("SRXY_FFMPEG_PATH", "").strip()
	if override:
		path = Path(override).expanduser()
		return path if path.is_file() else None
	vendor = vendor_ffmpeg_dir()
	if vendor is not None:
		candidate = vendor / "bin" / "ffmpeg"
		if candidate.is_file():
			return candidate
		legacy = vendor / "ffmpeg"
		if legacy.is_file():
			return legacy
	return None


def manifest_path(prefix: Path) -> Path:
	return prefix / MANIFEST_NAME


__all__ = [
	"DEFAULT_INSTALL_DIRNAME",
	"MANIFEST_NAME",
	"default_cache_root",
	"default_install_prefix",
	"manifest_path",
	"models_root",
	"resolve_ffmpeg_binary",
	"resolve_tessdata_prefix",
	"resolve_tesseract_binary",
	"srxy_home",
	"vendor_ffmpeg_dir",
	"vendor_root",
	"vendor_tesseract_dir",
]
