"""Check PyPI for newer srxy releases and run install-method-aware upgrades."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from srxy.adapters.inbound.installer.manifest import read_manifest
from srxy.adapters.inbound.installer.package_spec import (
	fetch_pypi_srxy_info,
	pypi_latest_version,
	version_newer,
)
from srxy.application.install_method import InstallMethod, detect_install_method
from srxy.application.install_paths import srxy_home


StatusCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class UpdateInfo:
	current_version: str
	latest_version: str
	update_available: bool
	method: InstallMethod


def installed_version() -> str:
	try:
		return package_version("srxy")
	except PackageNotFoundError:
		return "0.0.0"


def check_for_update(*, timeout: float = 15.0) -> UpdateInfo | None:
	"""Return update info, or None when PyPI cannot be reached."""
	info = fetch_pypi_srxy_info(timeout=timeout)
	if info is None:
		return None
	latest = pypi_latest_version(info)
	if latest is None:
		return None
	current = installed_version()
	method = detect_install_method()
	return UpdateInfo(
		current_version=current,
		latest_version=latest,
		update_available=version_newer(latest, current),
		method=method,
	)


def upgrade_command(method: InstallMethod | None = None, *, home: Path | None = None) -> list[str]:
	resolved = method if method is not None else detect_install_method()
	prefix = home if home is not None else srxy_home()
	if resolved is InstallMethod.DESKTOP_PREFIX and prefix is not None:
		uv = prefix / "vendor" / "uv" / "uv"
		uv_bin = str(uv) if uv.is_file() else (shutil.which("uv") or "uv")
		python = prefix / ".venv" / "bin" / "python"
		extras = ""
		manifest = read_manifest(prefix)
		if manifest is not None and manifest.semantic:
			extras = "[semantic]"
		return [uv_bin, "pip", "install", "-U", f"srxy{extras}", "--python", str(python)]
	if resolved is InstallMethod.UV_TOOL:
		uv = shutil.which("uv") or "uv"
		return [uv, "tool", "upgrade", "srxy"]
	if resolved is InstallMethod.PIPX:
		pipx = shutil.which("pipx") or "pipx"
		return [pipx, "upgrade", "srxy"]
	# pip / unknown — upgrade in the active environment
	uv = shutil.which("uv")
	if uv:
		return [uv, "pip", "install", "-U", "srxy"]
	return ["python", "-m", "pip", "install", "-U", "srxy"]


def apply_update(
	*,
	method: InstallMethod | None = None,
	status: StatusCallback | None = None,
) -> None:
	resolved = method if method is not None else detect_install_method()
	cmd = upgrade_command(resolved)
	if status is not None:
		status(f"Running: {' '.join(cmd)}")
	env = os.environ.copy()
	result = subprocess.run(  # noqa: S603
		cmd,
		capture_output=True,
		text=True,
		check=False,
		env=env,
	)
	if result.returncode != 0:
		detail = (result.stderr or result.stdout or "").strip()
		raise RuntimeError(f"Update failed ({result.returncode}): {' '.join(cmd)}\n{detail}")
	if status is not None:
		status("Update complete. Restart srxy to use the new version.")


__all__ = [
	"UpdateInfo",
	"apply_update",
	"check_for_update",
	"installed_version",
	"upgrade_command",
]
