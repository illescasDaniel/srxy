"""Installer version / compatibility metadata."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InstallerMeta:
	installer_version: str
	min_srxy_version: str


_DEFAULT = InstallerMeta(installer_version="1", min_srxy_version="1.6.0")


def _meta_candidates() -> list[Path]:
	candidates: list[Path] = []
	appdir = os.environ.get("APPDIR", "").strip()
	if appdir:
		candidates.append(Path(appdir) / "usr" / "share" / "srxy" / "installer_meta.toml")
	payload = os.environ.get("SRXY_INSTALLER_PAYLOAD", "").strip()
	if payload:
		candidates.append(Path(payload) / "share" / "srxy" / "installer_meta.toml")
	# Repo packaging/ when running from source
	root = Path(__file__).resolve().parents[5]
	candidates.append(root / "packaging" / "installer_meta.toml")
	# Packaged copy next to this module (optional)
	here = Path(__file__).resolve().parent
	candidates.append(here / "installer_meta.toml")
	return candidates


def _parse_meta(text: str) -> InstallerMeta:
	data = tomllib.loads(text)
	return InstallerMeta(
		installer_version=str(data.get("installer_version", _DEFAULT.installer_version)),
		min_srxy_version=str(data.get("min_srxy_version", _DEFAULT.min_srxy_version)),
	)


def load_installer_meta() -> InstallerMeta:
	for path in _meta_candidates():
		if path.is_file():
			try:
				return _parse_meta(path.read_text(encoding="utf-8"))
			except (OSError, tomllib.TOMLDecodeError, TypeError, ValueError):
				continue
	try:
		raw = (
			resources.files("srxy.adapters.inbound.installer")
			.joinpath("installer_meta.toml")
			.read_text(encoding="utf-8")
		)
		return _parse_meta(raw)
	except (FileNotFoundError, OSError, TypeError, tomllib.TOMLDecodeError, ValueError):
		return _DEFAULT


__all__ = [
	"InstallerMeta",
	"load_installer_meta",
]
