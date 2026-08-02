"""Uninstall a prefix install created by the desktop installer."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from srxy.adapters.inbound.installer.manifest import is_srxy_prefix, read_manifest
from srxy.application.install_paths import MANIFEST_NAME, default_install_prefix


StatusCallback = Callable[[str], None]

UNINSTALL_SEARCH_HINT = (
	f"Can't find the install? If another copy of srxy is available, search for the "
	f"marker file named {MANIFEST_NAME} under your home directory, for example:\n"
	f'  srxy "{MANIFEST_NAME}" ~\n'
	"Then run this installer again, choose Uninstall, and point it at that folder."
)


def discover_default_prefix() -> Path | None:
	candidate = default_install_prefix()
	if is_srxy_prefix(candidate):
		return candidate
	return None


def uninstall_prefix(prefix: Path, *, status: StatusCallback | None = None) -> None:
	resolved = prefix.expanduser().resolve()
	if not is_srxy_prefix(resolved):
		raise RuntimeError(
			f"Not an srxy install prefix (missing {MANIFEST_NAME} or bin/srxy): {resolved}\n\n{UNINSTALL_SEARCH_HINT}"
		)
	manifest = read_manifest(resolved)
	if status is not None:
		status(f"Removing {resolved}…")
	desktop = Path.home() / ".local" / "share" / "applications" / "srxy.desktop"
	if desktop.is_file():
		# Only remove if it points at this prefix.
		text = desktop.read_text(encoding="utf-8")
		if str(resolved) in text or (manifest and manifest.prefix and manifest.prefix in text):
			desktop.unlink(missing_ok=True)
			if status is not None:
				status("Removed desktop entry.")
	_remove_user_icons(status=status)
	from srxy.adapters.inbound.installer.path_setup import remove_srxy_path_from_shell

	if remove_srxy_path_from_shell():
		if status is not None:
			status("Removed terminal PATH shortcut.")
	shutil.rmtree(resolved)
	if status is not None:
		status("Uninstall complete.")


def _remove_user_icons(*, status: StatusCallback | None = None):
	icons_root = Path.home() / ".local" / "share" / "icons" / "hicolor"
	if not icons_root.is_dir():
		return
	removed = False
	for path in icons_root.glob("*/apps/srxy.png"):
		path.unlink(missing_ok=True)
		removed = True
	if removed and status is not None:
		status("Removed application icons.")


__all__ = [
	"UNINSTALL_SEARCH_HINT",
	"discover_default_prefix",
	"uninstall_prefix",
]
