"""Detect how srxy was installed (desktop prefix, uv tool, pipx, pip)."""

from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path

from srxy.application.install_paths import manifest_path, srxy_home


class InstallMethod(str, Enum):
	DESKTOP_PREFIX = "desktop_prefix"
	UV_TOOL = "uv_tool"
	PIPX = "pipx"
	PIP = "pip"
	UNKNOWN = "unknown"


def _path_looks_like_uv_tool(path: Path) -> bool:
	parts = {part.lower() for part in path.parts}
	text = str(path).lower()
	if "uv" in parts and "tools" in parts:
		return True
	return "/.local/share/uv/tools/" in text or "/uv/tools/" in text


def _path_looks_like_pipx(path: Path) -> bool:
	parts = {part.lower() for part in path.parts}
	text = str(path).lower()
	if "pipx" in parts:
		return True
	return "/.local/share/pipx/" in text or "/pipx/venvs/" in text


def detect_install_method(
	*,
	home: Path | None = None,
	executable: Path | None = None,
) -> InstallMethod:
	resolved_home = home if home is not None else srxy_home()
	if resolved_home is not None and manifest_path(resolved_home).is_file():
		return InstallMethod.DESKTOP_PREFIX
	if os.environ.get("SRXY_HOME", "").strip() and resolved_home is not None:
		# Prefix layout even before manifest is written (rare).
		if (resolved_home / ".venv").is_dir():
			return InstallMethod.DESKTOP_PREFIX

	exe = executable if executable is not None else Path(sys.executable).resolve()
	if _path_looks_like_uv_tool(exe):
		return InstallMethod.UV_TOOL
	if _path_looks_like_pipx(exe):
		return InstallMethod.PIPX
	# Editable / venv / system pip-style installs
	if "site-packages" in str(exe).lower() or (exe.parent / "pip").exists() or exe.name.startswith("python"):
		return InstallMethod.PIP
	return InstallMethod.UNKNOWN


def semantic_enable_hint(method: InstallMethod | None = None) -> str:
	"""Short user-facing instruction to enable AI / OCR extras."""
	from srxy.i18n import tr

	resolved = method if method is not None else detect_install_method()
	if resolved is InstallMethod.DESKTOP_PREFIX:
		return tr("hint.semantic.desktop")
	if resolved is InstallMethod.UV_TOOL:
		return tr("hint.semantic.uv_tool")
	if resolved is InstallMethod.PIPX:
		return tr("hint.semantic.pipx")
	return tr("hint.semantic.pip")


def ocr_enable_hint(method: InstallMethod | None = None) -> str:
	from srxy.i18n import tr

	resolved = method if method is not None else detect_install_method()
	if resolved is InstallMethod.DESKTOP_PREFIX:
		return tr("hint.ocr.desktop")
	return tr("hint.ocr.default")


def ffmpeg_enable_hint(method: InstallMethod | None = None) -> str:
	from srxy.i18n import tr

	resolved = method if method is not None else detect_install_method()
	if resolved is InstallMethod.DESKTOP_PREFIX:
		return tr("hint.ffmpeg.desktop")
	return tr("hint.ffmpeg.default")


__all__ = [
	"InstallMethod",
	"detect_install_method",
	"ffmpeg_enable_hint",
	"ocr_enable_hint",
	"semantic_enable_hint",
]
