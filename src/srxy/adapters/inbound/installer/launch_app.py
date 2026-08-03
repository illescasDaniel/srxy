"""Launch the installed srxy app from a prefix."""

from __future__ import annotations

import subprocess
from pathlib import Path


def installed_launcher_path(prefix: Path | str) -> Path:
	return Path(prefix).expanduser().resolve() / "bin" / "srxy"


def launch_installed_app(prefix: Path | str):
	"""Start the installed GUI/TUI entrypoint detached from the installer process."""
	launcher = installed_launcher_path(prefix)
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


__all__ = ["installed_launcher_path", "launch_installed_app"]
