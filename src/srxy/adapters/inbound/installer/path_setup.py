"""Idempotent PATH helpers for prefix ``bin/`` (shell rc on Unix, user PATH on Windows)."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


PATH_BEGIN = "# >>> srxy PATH >>>"
PATH_END = "# <<< srxy PATH <<<"
# Sentinel stored in InstallManifest.path_rc on Windows (not a filesystem path).
WINDOWS_USER_PATH_MARKER = "windows:user-path"
# Lowercase suffix used when scanning HKCU Path for uninstall without a recorded bin dir.
DEFAULT_SRXY_BIN_SUFFIX = "srxy\\bin"


@dataclass(frozen=True, slots=True)
class PathBlockRemovalResult:
	changed: bool
	incomplete_block: bool = False


def _is_windows() -> bool:
	return platform.system().lower() == "windows"


def detect_login_shell() -> str:
	env_shell = os.environ.get("SHELL", "").strip()
	if env_shell:
		return Path(env_shell).name
	try:
		import pwd

		entry = pwd.getpwuid(os.getuid())
		if entry.pw_shell:
			return Path(entry.pw_shell).name
	except (ImportError, KeyError, AttributeError):
		pass
	return "bash"


def shell_rc_path(shell: str | None = None) -> Path:
	name = (shell or detect_login_shell()).lower()
	home = Path.home()
	if "zsh" in name:
		return home / ".zshrc"
	if "fish" in name:
		return home / ".config" / "fish" / "config.fish"
	# bash and unknown → .bashrc (also create if missing)
	return home / ".bashrc"


def _block_for_shell(bin_dir: Path, *, shell_name: str) -> str:
	bin_text = str(bin_dir)
	if "fish" in shell_name.lower():
		body = f'set -gx PATH "{bin_text}" $PATH'
	else:
		body = f'export PATH="{bin_text}:$PATH"'
	return f"{PATH_BEGIN}\n{body}\n{PATH_END}\n"


def remove_path_block(rc_path: Path) -> PathBlockRemovalResult:
	"""Remove an existing srxy PATH block. Leaves the file intact if the end marker is missing."""
	if not rc_path.is_file():
		return PathBlockRemovalResult(changed=False)
	try:
		text = rc_path.read_text(encoding="utf-8")
	except OSError:
		return PathBlockRemovalResult(changed=False)
	begin = text.find(PATH_BEGIN)
	if begin < 0:
		return PathBlockRemovalResult(changed=False)
	end = text.find(PATH_END, begin)
	if end < 0:
		return PathBlockRemovalResult(changed=False, incomplete_block=True)
	end += len(PATH_END)
	while end < len(text) and text[end] == "\n":
		end += 1
	new_text = text[:begin] + text[end:]
	new_text = new_text.rstrip() + ("\n" if new_text.strip() else "")
	if new_text == text:
		return PathBlockRemovalResult(changed=False)
	rc_path.write_text(new_text, encoding="utf-8")
	return PathBlockRemovalResult(changed=True)


def _read_user_path() -> str:
	import winreg

	with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
		try:
			value, _ = winreg.QueryValueEx(key, "Path")
		except FileNotFoundError:
			return ""
	return str(value or "")


def _write_user_path(value: str):
	import ctypes
	import winreg

	with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE) as key:
		winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, value)
	# Notify running processes that the environment changed (best-effort).
	hwnd_broadcast = 0xFFFF
	wm_settingchange = 0x001A
	smto_abortifhung = 0x0002
	result = ctypes.c_long()
	ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
		hwnd_broadcast,
		wm_settingchange,
		0,
		"Environment",
		smto_abortifhung,
		5000,
		ctypes.byref(result),
	)


def _path_entries(raw: str) -> list[str]:
	return [part for part in raw.split(";") if part.strip()]


def ensure_windows_user_path(bin_dir: Path) -> str:
	"""Add ``bin_dir`` to the per-user PATH if missing. Returns the Windows marker string."""
	resolved = str(bin_dir.expanduser().resolve())
	current = _read_user_path()
	entries = _path_entries(current)
	normalized = {entry.rstrip("\\/").lower() for entry in entries}
	if resolved.rstrip("\\/").lower() not in normalized:
		entries.append(resolved)
		_write_user_path(";".join(entries))
	# Keep process PATH updated for the rest of this installer run.
	process_parts = _path_entries(os.environ.get("PATH", ""))
	process_norm = {part.rstrip("\\/").lower() for part in process_parts}
	if resolved.rstrip("\\/").lower() not in process_norm:
		os.environ["PATH"] = resolved + (";" + os.environ["PATH"] if os.environ.get("PATH") else "")
	return WINDOWS_USER_PATH_MARKER


def remove_windows_user_path(bin_dir: Path | None = None) -> PathBlockRemovalResult:
	"""Remove ``bin_dir`` (or any ``...\\srxy\\bin``) from the per-user PATH."""
	current = _read_user_path()
	if not current.strip():
		return PathBlockRemovalResult(changed=False)
	target = None
	if bin_dir is not None:
		target = str(bin_dir.expanduser().resolve()).rstrip("\\/").lower()
	kept: list[str] = []
	changed = False
	for entry in _path_entries(current):
		norm = entry.rstrip("\\/").lower()
		drop = False
		if target is not None and norm == target:
			drop = True
		elif target is None and norm.endswith(f"\\{DEFAULT_SRXY_BIN_SUFFIX}"):
			drop = True
		elif target is None and norm.endswith(f"/{DEFAULT_SRXY_BIN_SUFFIX}".replace("/", "\\")):
			drop = True
		if drop:
			changed = True
			continue
		kept.append(entry)
	if not changed:
		return PathBlockRemovalResult(changed=False)
	_write_user_path(";".join(kept))
	return PathBlockRemovalResult(changed=True)


def ensure_path_block(
	bin_dir: Path,
	*,
	shell_name: str | None = None,
	rc_path: Path | None = None,
) -> Path | str:
	"""Write or refresh PATH for the prefix bin dir.

	Returns the shell rc path on Unix, or :data:`WINDOWS_USER_PATH_MARKER` on Windows.
	When ``rc_path`` is passed explicitly, always write a shell-style block (used by tests
	and unusual hosts), even on Windows.
	"""
	if _is_windows() and rc_path is None:
		return ensure_windows_user_path(bin_dir)
	resolved_shell = shell_name or detect_login_shell()
	target = rc_path if rc_path is not None else shell_rc_path(resolved_shell)
	target.parent.mkdir(parents=True, exist_ok=True)
	block = _block_for_shell(bin_dir.expanduser().resolve(), shell_name=resolved_shell)
	existing = ""
	if target.is_file():
		remove_path_block(target)
		if target.is_file():
			existing = target.read_text(encoding="utf-8")
	if existing and not existing.endswith("\n"):
		existing += "\n"
	if existing and not existing.endswith("\n\n"):
		existing += "\n"
	target.write_text(existing + block, encoding="utf-8")
	return target


def remove_srxy_path_from_shell(
	*,
	shell_name: str | None = None,
	rc_path: Path | str | None = None,
	bin_dir: Path | None = None,
) -> PathBlockRemovalResult:
	if _is_windows():
		marker = str(rc_path).strip() if rc_path is not None else ""
		if marker == WINDOWS_USER_PATH_MARKER or (marker == "" and bin_dir is not None):
			return remove_windows_user_path(bin_dir)
		if marker and marker != WINDOWS_USER_PATH_MARKER:
			# Explicit filesystem rc path (tests / unusual setups).
			return remove_path_block(Path(rc_path))  # ty: ignore[invalid-argument-type]
		return remove_windows_user_path(bin_dir)
	target = Path(rc_path) if rc_path is not None else shell_rc_path(shell_name)
	return remove_path_block(target)


__all__ = [
	"PATH_BEGIN",
	"PATH_END",
	"WINDOWS_USER_PATH_MARKER",
	"PathBlockRemovalResult",
	"detect_login_shell",
	"ensure_path_block",
	"ensure_windows_user_path",
	"remove_path_block",
	"remove_srxy_path_from_shell",
	"remove_windows_user_path",
	"shell_rc_path",
]
