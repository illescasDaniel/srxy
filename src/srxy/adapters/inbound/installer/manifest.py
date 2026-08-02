"""Install-prefix manifest for the desktop installer / uninstaller."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from srxy.application.install_paths import MANIFEST_NAME, manifest_path


@dataclass(slots=True)
class InstallManifest:
	version: str
	prefix: str
	installed_at: str
	semantic: bool = False
	models_prefetched: bool = False
	vendor_tesseract: bool = False
	vendor_ffmpeg: bool = False
	extra: dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		payload = asdict(self)
		extra = payload.pop("extra", {})
		payload.update(extra)
		return payload

	@staticmethod
	def from_dict(data: dict[str, Any]) -> InstallManifest:
		known = {
			"version",
			"prefix",
			"installed_at",
			"semantic",
			"models_prefetched",
			"vendor_tesseract",
			"vendor_ffmpeg",
		}
		extra = {key: value for key, value in data.items() if key not in known}
		return InstallManifest(
			version=str(data.get("version", "")),
			prefix=str(data.get("prefix", "")),
			installed_at=str(data.get("installed_at", "")),
			semantic=bool(data.get("semantic", False)),
			models_prefetched=bool(data.get("models_prefetched", False)),
			vendor_tesseract=bool(data.get("vendor_tesseract", False)),
			vendor_ffmpeg=bool(data.get("vendor_ffmpeg", False)),
			extra=extra,
		)


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_manifest(prefix: Path, manifest: InstallManifest):
	prefix.mkdir(parents=True, exist_ok=True)
	path = manifest_path(prefix)
	path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(prefix: Path) -> InstallManifest | None:
	path = manifest_path(prefix)
	if not path.is_file():
		return None
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError):
		return None
	if not isinstance(data, dict):
		return None
	return InstallManifest.from_dict(data)


def is_srxy_prefix(prefix: Path) -> bool:
	return read_manifest(prefix) is not None or (prefix / "bin" / "srxy").is_file()


__all__ = [
	"InstallManifest",
	"MANIFEST_NAME",
	"is_srxy_prefix",
	"read_manifest",
	"utc_now_iso",
	"write_manifest",
]
