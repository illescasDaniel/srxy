"""Uninstall a prefix install created by the desktop installer."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

from srxy.adapters.inbound.installer.manifest import (
	InstallManifest,
	is_srxy_prefix,
	looks_like_partial_srxy_prefix,
	prefix_needs_confirmation,
	require_matching_manifest,
)
from srxy.application.install_paths import MANIFEST_NAME, default_install_prefix, default_non_prefix_cache_root
from srxy.i18n import tr


StatusCallback = Callable[[str], None]


def uninstall_search_hint() -> str:
	return tr(
		"installer.uninstall.search_hint",
		manifest_name=MANIFEST_NAME,
	)


def discover_default_prefix() -> Path | None:
	candidate = default_install_prefix()
	if is_srxy_prefix(candidate) or looks_like_partial_srxy_prefix(candidate):
		return candidate
	return None


def _validate_uninstall_prefix(prefix: Path, *, confirm_unsafe: bool):
	if prefix_needs_confirmation(prefix) and not confirm_unsafe:
		raise RuntimeError(tr("installer.error.unsafe_prefix"))


def _remove_desktop_if_matches(resolved: Path, *, recorded_prefix: str = "", status: StatusCallback | None = None):
	desktop = Path.home() / ".local" / "share" / "applications" / "srxy.desktop"
	if not desktop.is_file():
		return
	text = desktop.read_text(encoding="utf-8")
	if str(resolved) in text or (recorded_prefix and recorded_prefix in text):
		desktop.unlink(missing_ok=True)
		if status is not None:
			status(tr("installer.status.removed_desktop_entry"))


def cleanup_user_data(
	*,
	remove_cache: bool = True,
	remove_settings: bool = True,
	remove_models: bool = True,
	status: StatusCallback | None = None,
) -> None:
	"""Remove srxy-managed user data outside an install prefix (prefix tree is separate)."""
	prior_home = os.environ.pop("SRXY_HOME", None)
	try:
		if remove_cache:
			from srxy.adapters.outbound.cache.cache import clear_results_cache

			clear_results_cache()
			bootstrap = default_non_prefix_cache_root() / "online-bootstrap"
			if bootstrap.is_dir():
				shutil.rmtree(bootstrap, ignore_errors=True)
				if status is not None:
					status(tr("installer.status.removed_bootstrap_cache"))
			if status is not None:
				status(tr("installer.status.removed_cache"))
		if remove_models:
			from srxy.adapters.outbound.models.model_store import clear_all_models

			clear_all_models()
			if status is not None:
				status(tr("installer.status.removed_models"))
		if remove_settings:
			from srxy.application.settings import reset_settings

			reset_settings()
			if status is not None:
				status(tr("installer.status.removed_settings"))
	finally:
		if prior_home is not None:
			os.environ["SRXY_HOME"] = prior_home


def uninstall_prefix(
	prefix: Path,
	*,
	status: StatusCallback | None = None,
	confirm_unsafe: bool = False,
	remove_cache: bool = True,
	remove_settings: bool = True,
	remove_models: bool = True,
) -> None:
	resolved = prefix.expanduser().resolve()
	_validate_uninstall_prefix(resolved, confirm_unsafe=confirm_unsafe)
	if is_srxy_prefix(resolved):
		manifest = require_matching_manifest(resolved)
		_remove_desktop_if_matches(resolved, recorded_prefix=manifest.prefix, status=status)
		_remove_user_icons(manifest, status=status)
		from srxy.adapters.inbound.installer.path_setup import (
			WINDOWS_USER_PATH_MARKER,
			remove_srxy_path_from_shell,
		)

		rc_raw = manifest.path_rc.strip()
		if rc_raw == WINDOWS_USER_PATH_MARKER:
			result = remove_srxy_path_from_shell(
				rc_path=WINDOWS_USER_PATH_MARKER,
				bin_dir=resolved / "bin",
			)
		else:
			rc_path = Path(rc_raw).expanduser() if rc_raw else None
			result = remove_srxy_path_from_shell(rc_path=rc_path)
		if result.incomplete_block and status is not None:
			status(tr("installer.status.path_incomplete_block"))
		elif result.changed and status is not None:
			status(tr("installer.status.removed_path"))
		if status is not None:
			status(tr("installer.status.removing_app"))
		shutil.rmtree(resolved)
		cleanup_user_data(
			remove_cache=remove_cache,
			remove_settings=remove_settings,
			remove_models=remove_models,
			status=status,
		)
		if status is not None:
			status(tr("installer.status.uninstall_complete"))
		return

	if looks_like_partial_srxy_prefix(resolved):
		_remove_desktop_if_matches(resolved, status=status)
		if status is not None:
			status(tr("installer.status.reclaiming_partial"))
		shutil.rmtree(resolved)
		cleanup_user_data(
			remove_cache=remove_cache,
			remove_settings=remove_settings,
			remove_models=remove_models,
			status=status,
		)
		if status is not None:
			status(tr("installer.status.uninstall_complete"))
		return

	hint = uninstall_search_hint()
	raise RuntimeError(
		f"{tr('installer.error.missing_manifest', manifest_name=MANIFEST_NAME, path=str(resolved))}\n\n{hint}"
	)


def _remove_user_icons(manifest: InstallManifest, *, status: StatusCallback | None = None):
	removed = False
	for raw in manifest.user_icons:
		path = Path(raw).expanduser()
		if path.is_file():
			path.unlink(missing_ok=True)
			removed = True
	if removed and status is not None:
		status(tr("installer.status.removed_icons"))


__all__ = [
	"cleanup_user_data",
	"discover_default_prefix",
	"uninstall_prefix",
	"uninstall_search_hint",
]
