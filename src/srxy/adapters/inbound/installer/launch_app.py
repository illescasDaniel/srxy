"""Launch the installed srxy app from a prefix."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


# Brief pause before installer teardown so first Qt/dyld map is less contended.
LAUNCH_TEARDOWN_DELAY_SECONDS = 2.5


def installed_launcher_path(prefix: Path | str) -> Path:
	root = Path(prefix).expanduser().resolve()
	if platform.system().lower() == "darwin":
		app_exe = root / "Srxy.app" / "Contents" / "MacOS" / "srxy"
		if app_exe.is_file():
			return app_exe
	return root / "bin" / "srxy"


def installed_macos_app_bundle(prefix: Path | str) -> Path | None:
	root = Path(prefix).expanduser().resolve()
	app_bundle = root / "Srxy.app"
	if (app_bundle / "Contents" / "MacOS" / "srxy").is_file():
		return app_bundle
	return None


def launch_installed_app(prefix: Path | str):
	"""Start the installed GUI/TUI entrypoint detached from the installer process."""
	root = Path(prefix).expanduser().resolve()
	if platform.system().lower() == "darwin":
		app_bundle = installed_macos_app_bundle(root)
		if app_bundle is not None:
			open_bin = shutil.which("open") or "/usr/bin/open"
			subprocess.Popen(  # noqa: S603 — LaunchServices open for Srxy.app
				[open_bin, str(app_bundle)],
				cwd=str(Path.home()),
				stdin=subprocess.DEVNULL,
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				start_new_session=True,
			)
			return

	launcher = installed_launcher_path(root)
	if not launcher.is_file():
		raise FileNotFoundError(f"srxy launcher not found at {launcher}")
	subprocess.Popen(  # noqa: S603 — launches the installer-written prefix binary
		[str(launcher)],
		cwd=str(Path.home()),
		stdin=subprocess.DEVNULL,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
		start_new_session=True,
	)


__all__ = [
	"LAUNCH_TEARDOWN_DELAY_SECONDS",
	"installed_launcher_path",
	"installed_macos_app_bundle",
	"launch_installed_app",
]
