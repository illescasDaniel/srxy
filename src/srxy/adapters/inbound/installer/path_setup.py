"""Idempotent shell PATH helpers for prefix ``bin/``."""

from __future__ import annotations

import os
import pwd
import shutil
from pathlib import Path


PATH_BEGIN = "# >>> srxy PATH >>>"
PATH_END = "# <<< srxy PATH <<<"


def detect_login_shell() -> str:
	env_shell = os.environ.get("SHELL", "").strip()
	if env_shell:
		return Path(env_shell).name
	try:
		entry = pwd.getpwuid(os.getuid())
		if entry.pw_shell:
			return Path(entry.pw_shell).name
	except KeyError:
		pass
	if shutil.which("getent"):
		# Best-effort; ignore failures
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


def remove_path_block(rc_path: Path) -> bool:
	"""Remove an existing srxy PATH block. Returns True if the file changed."""
	if not rc_path.is_file():
		return False
	try:
		text = rc_path.read_text(encoding="utf-8")
	except OSError:
		return False
	begin = text.find(PATH_BEGIN)
	if begin < 0:
		return False
	end = text.find(PATH_END, begin)
	if end < 0:
		# Truncate from marker to EOF if end marker missing
		new_text = text[:begin].rstrip() + ("\n" if text[:begin].strip() else "")
	else:
		end += len(PATH_END)
		while end < len(text) and text[end] == "\n":
			end += 1
		new_text = text[:begin] + text[end:]
		new_text = new_text.rstrip() + ("\n" if new_text.strip() else "")
	if new_text == text:
		return False
	rc_path.write_text(new_text, encoding="utf-8")
	return True


def ensure_path_block(
	bin_dir: Path,
	*,
	shell_name: str | None = None,
	rc_path: Path | None = None,
) -> Path:
	"""Write or refresh the PATH block in the shell rc. Returns the rc path."""
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


def remove_srxy_path_from_shell(*, shell_name: str | None = None, rc_path: Path | None = None) -> bool:
	target = rc_path if rc_path is not None else shell_rc_path(shell_name)
	return remove_path_block(target)


__all__ = [
	"PATH_BEGIN",
	"PATH_END",
	"detect_login_shell",
	"ensure_path_block",
	"remove_path_block",
	"remove_srxy_path_from_shell",
	"shell_rc_path",
]
