"""macOS packaging resources (app launcher source, etc.)."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def app_launcher_c_path() -> Path:
	"""Return the packaged ``SrxyAppLauncher.c`` path used to build ``Srxy.app``."""
	return Path(str(resources.files("srxy.resources.macos"))) / "SrxyAppLauncher.c"
