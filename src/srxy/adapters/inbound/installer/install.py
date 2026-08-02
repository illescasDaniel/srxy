"""Perform a prefix install of srxy (uv venv + optional vendor/semantic)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version as package_version
from pathlib import Path

from srxy.adapters.inbound.installer.download import ProgressCallback
from srxy.adapters.inbound.installer.manifest import InstallManifest, utc_now_iso, write_manifest
from srxy.adapters.inbound.installer.package_spec import resolve_srxy_install_spec, with_semantic_extra
from srxy.adapters.inbound.installer.vendor import install_ffmpeg, install_tesseract, install_uv
from srxy.application.install_paths import MANIFEST_NAME
from srxy.resources.icons import app_icon_path, available_icon_sizes


StatusCallback = Callable[[str], None]


@dataclass(slots=True)
class InstallOptions:
	prefix: Path
	download_tesseract: bool = True
	download_ffmpeg: bool = True
	install_semantic: bool = False
	prefetch_models: bool = False
	add_to_path: bool = True
	srxy_spec: str = ""


def _status(callback: StatusCallback | None, message: str):
	if callback is not None:
		callback(message)


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
	result = subprocess.run(  # noqa: S603
		cmd,
		capture_output=True,
		text=True,
		check=False,
		env=env,
	)
	if result.returncode != 0:
		detail = (result.stderr or result.stdout or "").strip()
		raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")


def _write_launcher(prefix: Path):
	bin_dir = prefix / "bin"
	bin_dir.mkdir(parents=True, exist_ok=True)
	log_dir = prefix / "logs"
	log_dir.mkdir(parents=True, exist_ok=True)
	venv_srxy = prefix / ".venv" / "bin" / "srxy"
	launcher = bin_dir / "srxy"
	vendor_bin_parts = [
		str(prefix / "vendor" / "tesseract" / "bin"),
		str(prefix / "vendor" / "ffmpeg" / "bin"),
		str(prefix / "vendor" / "uv"),
	]
	path_prefix = ":".join(vendor_bin_parts)
	tessdata = prefix / "vendor" / "tesseract" / "tessdata"
	log_file = log_dir / "srxy.log"
	content = f"""#!/bin/sh
set -eu
SRXY_HOME="{prefix}"
export SRXY_HOME
export PATH="{path_prefix}:${{PATH}}"
if [ -d "{tessdata}" ]; then
	export TESSDATA_PREFIX="{tessdata}"
fi
LOG_DIR="{log_dir}"
LOG_FILE="{log_file}"
mkdir -p "$LOG_DIR"
{{
	echo "===== $(date -Iseconds 2>/dev/null || date) srxy start ====="
	echo "argv: $*"
	echo "SRXY_HOME=$SRXY_HOME"
}} >>"$LOG_FILE"
# Keep GUI stdout/stderr in the install folder for easy debugging.
exec "{venv_srxy}" "$@" >>"$LOG_FILE" 2>&1
"""
	launcher.write_text(content, encoding="utf-8")
	launcher.chmod(0o755)


def _install_icons(prefix: Path) -> Path:
	"""Copy hicolor icons into the prefix and user icon theme."""
	share_icons = prefix / "share" / "icons" / "hicolor"
	user_icons = Path.home() / ".local" / "share" / "icons" / "hicolor"
	sizes = available_icon_sizes() or [256]
	installed_256 = share_icons / "256x256" / "apps" / "srxy.png"
	for size in sizes:
		source = app_icon_path(size=size)
		for root in (share_icons, user_icons):
			target_dir = root / f"{size}x{size}" / "apps"
			target_dir.mkdir(parents=True, exist_ok=True)
			shutil.copy2(source, target_dir / "srxy.png")
	# Scalable/fallback copy of the master asset under 512 if present.
	master = app_icon_path()
	for root in (share_icons, user_icons):
		target_dir = root / "512x512" / "apps"
		target_dir.mkdir(parents=True, exist_ok=True)
		shutil.copy2(master, target_dir / "srxy.png")
	return installed_256 if installed_256.is_file() else app_icon_path(size=256)


def _write_desktop_entry(prefix: Path):
	_install_icons(prefix)
	apps = Path.home() / ".local" / "share" / "applications"
	apps.mkdir(parents=True, exist_ok=True)
	desktop = apps / "srxy.desktop"
	exec_path = prefix / "bin" / "srxy"
	desktop.write_text(
		"\n".join(
			[
				"[Desktop Entry]",
				"Type=Application",
				"Name=srxy",
				"Comment=Find files by what you mean",
				f"Exec={exec_path}",
				"Icon=srxy",
				"Terminal=false",
				"Categories=Utility;FileTools;",
				"StartupNotify=true",
				"",
			]
		),
		encoding="utf-8",
	)


def _resolve_uv(prefix: Path) -> Path:
	vendor_uv = prefix / "vendor" / "uv" / "uv"
	if vendor_uv.is_file():
		return vendor_uv
	which = shutil.which("uv")
	if which:
		return Path(which)
	raise RuntimeError("uv is not available; vendor install failed")


def _package_version(venv: Path | None = None) -> str:
	if venv is not None:
		python = venv / "bin" / "python"
		if python.is_file():
			result = subprocess.run(  # noqa: S603
				[str(python), "-c", "from importlib.metadata import version; print(version('srxy'))"],
				capture_output=True,
				text=True,
				check=False,
			)
			if result.returncode == 0 and result.stdout.strip():
				return result.stdout.strip()
	try:
		return package_version("srxy")
	except Exception:
		return "unknown"


def install_srxy(
	options: InstallOptions,
	*,
	status: StatusCallback | None = None,
	progress: ProgressCallback | None = None,
) -> InstallManifest:
	prefix = options.prefix.expanduser().resolve()
	prefix.mkdir(parents=True, exist_ok=True)
	(prefix / "logs").mkdir(parents=True, exist_ok=True)

	_status(status, "Installing uv…")
	install_uv(prefix, progress=progress)
	uv = _resolve_uv(prefix)

	_status(status, "Creating Python environment…")
	venv = prefix / ".venv"
	_run([str(uv), "venv", "--clear", "--python", "3.12", str(venv)])

	env = os.environ.copy()
	env["VIRTUAL_ENV"] = str(venv)
	env["PATH"] = f"{venv / 'bin'}:{env.get('PATH', '')}"

	spec = (options.srxy_spec or "").strip() or resolve_srxy_install_spec()
	if options.install_semantic:
		spec = with_semantic_extra(spec)

	_status(status, f"Installing {spec}…")
	_run([str(uv), "pip", "install", spec], env=env)

	# Ensure GUI dependency is present (guards against stale PyPI metadata).
	probe = subprocess.run(  # noqa: S603
		[str(venv / "bin" / "python"), "-c", "import PySide6"],
		capture_output=True,
		text=True,
		check=False,
		env=env,
	)
	if probe.returncode != 0:
		raise RuntimeError(
			"Installed srxy is missing PySide6 (GUI). The installer must use a local "
			"wheel/source build that includes the desktop UI — not an older PyPI build.\n"
			f"{(probe.stderr or probe.stdout).strip()}"
		)

	vendor_tesseract = False
	vendor_ffmpeg = False
	if options.download_tesseract:
		_status(status, "Downloading Tesseract…")
		install_tesseract(prefix, progress=progress)
		vendor_tesseract = True
	if options.download_ffmpeg:
		_status(status, "Downloading ffmpeg…")
		install_ffmpeg(prefix, progress=progress)
		vendor_ffmpeg = True

	models_prefetched = False
	if options.install_semantic and options.prefetch_models:
		_status(status, "Prefetching AI models…")
		env["SRXY_HOME"] = str(prefix)
		env["SRXY_AUTO_DOWNLOAD"] = "1"
		_run([str(venv / "bin" / "python"), "-m", "srxy.adapters.outbound.models.model_store", "all"], env=env)
		models_prefetched = True

	_status(status, "Writing launcher and desktop entry…")
	_write_launcher(prefix)
	_write_desktop_entry(prefix)

	if options.add_to_path:
		from srxy.adapters.inbound.installer.path_setup import ensure_path_block

		_status(status, "Adding terminal PATH shortcut…")
		rc = ensure_path_block(prefix / "bin")
		_status(status, f"PATH updated in {rc} (open a new terminal to use `srxy`).")

	manifest = InstallManifest(
		version=_package_version(venv),
		prefix=str(prefix),
		installed_at=utc_now_iso(),
		semantic=options.install_semantic,
		models_prefetched=models_prefetched,
		vendor_tesseract=vendor_tesseract,
		vendor_ffmpeg=vendor_ffmpeg,
		extra={
			"python": sys.version.split()[0],
			"marker": MANIFEST_NAME,
			"srxy_spec": spec,
		},
	)
	write_manifest(prefix, manifest)
	_status(status, "Install complete.")
	return manifest


__all__ = [
	"InstallOptions",
	"install_srxy",
]
