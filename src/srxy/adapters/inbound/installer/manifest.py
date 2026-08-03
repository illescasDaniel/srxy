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
	path_rc: str = ""
	installer_version: str = ""
	privacy_ack_version: str = ""
	user_icons: list[str] = field(default_factory=list)
	extra: dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		payload = asdict(self)
		extra = payload.pop("extra", {})
		user_icons = payload.pop("user_icons", [])
		if user_icons:
			payload["user_icons"] = user_icons
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
			"path_rc",
			"installer_version",
			"privacy_ack_version",
			"user_icons",
		}
		extra = {key: value for key, value in data.items() if key not in known}
		raw_icons = data.get("user_icons", [])
		user_icons = [str(item) for item in raw_icons] if isinstance(raw_icons, list) else []
		return InstallManifest(
			version=str(data.get("version", "")),
			prefix=str(data.get("prefix", "")),
			installed_at=str(data.get("installed_at", "")),
			semantic=bool(data.get("semantic", False)),
			models_prefetched=bool(data.get("models_prefetched", False)),
			vendor_tesseract=bool(data.get("vendor_tesseract", False)),
			vendor_ffmpeg=bool(data.get("vendor_ffmpeg", False)),
			path_rc=str(data.get("path_rc", "")),
			installer_version=str(data.get("installer_version", "")),
			privacy_ack_version=str(data.get("privacy_ack_version", "")),
			user_icons=user_icons,
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


def _resolve_path(path: Path) -> Path:
	return path.expanduser().resolve()


def is_srxy_prefix(prefix: Path) -> bool:
	manifest = read_manifest(prefix)
	if manifest is None:
		return False
	recorded = manifest.prefix.strip()
	if not recorded:
		return False
	try:
		return _resolve_path(Path(recorded)) == _resolve_path(prefix)
	except OSError:
		return False


def prefix_needs_confirmation(prefix: Path) -> bool:
	resolved = _resolve_path(prefix)
	home = _resolve_path(Path.home())
	if resolved == home:
		return True
	if resolved.parent == home and resolved.name.startswith("."):
		return True
	try:
		resolved.relative_to(home)
	except ValueError:
		return True
	return False


def is_non_empty_foreign_prefix(prefix: Path) -> bool:
	if not prefix.is_dir():
		return False
	if is_srxy_prefix(prefix):
		return False
	try:
		return any(prefix.iterdir())
	except OSError:
		return True


def looks_like_partial_srxy_prefix(prefix: Path) -> bool:
	"""True when the folder looks like a broken / incomplete srxy install.

	Valid installs (``is_srxy_prefix``) are not partial. Markers include a
	venv, vendor uv, launcher, or any install manifest (including invalid).
	"""
	if not prefix.is_dir():
		return False
	if is_srxy_prefix(prefix):
		return False
	resolved = _resolve_path(prefix)
	markers = (
		resolved / ".venv",
		resolved / "vendor" / "uv",
		resolved / "bin" / "srxy",
		manifest_path(resolved),
	)
	return any(path.exists() for path in markers)


def require_matching_manifest(prefix: Path) -> InstallManifest:
	resolved = _resolve_path(prefix)
	manifest = read_manifest(resolved)
	if manifest is None:
		from srxy.i18n import tr

		raise RuntimeError(
			tr(
				"installer.error.missing_manifest",
				manifest_name=MANIFEST_NAME,
				path=str(resolved),
			)
		)
	recorded = manifest.prefix.strip()
	if not recorded:
		from srxy.i18n import tr

		raise RuntimeError(tr("installer.error.empty_manifest_prefix", path=str(resolved)))
	try:
		if _resolve_path(Path(recorded)) != resolved:
			from srxy.i18n import tr

			raise RuntimeError(
				tr(
					"installer.error.prefix_mismatch",
					path=str(resolved),
					recorded=recorded,
				)
			)
	except OSError as exc:
		from srxy.i18n import tr

		raise RuntimeError(tr("installer.error.invalid_manifest_prefix", path=str(resolved))) from exc
	return manifest


__all__ = [
	"InstallManifest",
	"MANIFEST_NAME",
	"is_non_empty_foreign_prefix",
	"is_srxy_prefix",
	"looks_like_partial_srxy_prefix",
	"prefix_needs_confirmation",
	"read_manifest",
	"require_matching_manifest",
	"utc_now_iso",
	"write_manifest",
]
