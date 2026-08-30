#!/usr/bin/env python3
"""Rewrite absolute project paths inside a copied uv/virtualenv tree.

After rsync/robocopy of .venv into a worktree, console-script shebangs,
activate scripts, editable .pth files, and direct_url.json still point at the
primary checkout. ``uv sync`` does not fix those
(https://github.com/astral-sh/uv/issues/18196). This helper rewrites them
in place. On Windows it also updates UV_PYTHON_PATH PE resources in uv
trampoline .exe files when they reference the old venv python.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _path_variants(root: Path) -> list[str]:
	"""Return string forms of *root* worth searching/replacing."""
	variants: list[str] = []
	for candidate in (root.resolve(), root):
		as_posix = candidate.as_posix()
		as_native = str(candidate)
		for form in (as_posix, as_native):
			if form and form not in variants:
				variants.append(form)
			bs = form.replace("/", "\\")
			if bs != form and bs not in variants:
				variants.append(bs)
	return variants


def _build_replacements(old_root: Path, new_root: Path) -> list[tuple[str, str]]:
	"""Longest-first (old, new) string pairs covering path + file:// forms."""
	pairs: list[tuple[str, str]] = []
	new_resolved = new_root.resolve()
	new_posix = new_resolved.as_posix()
	new_native = str(new_resolved)
	new_bs = new_native.replace("/", "\\")

	for old in _path_variants(old_root):
		if "\\" in old and "/" not in old:
			new = new_bs
		elif "\\" in old:
			new = new_native
		else:
			new = new_posix
		if old != new and (old, new) not in pairs:
			pairs.append((old, new))
		old_url = "file://" + old.replace("\\", "/")
		new_url = "file://" + new_posix
		if old_url != new_url and (old_url, new_url) not in pairs:
			pairs.append((old_url, new_url))

	pairs.sort(key=lambda p: len(p[0]), reverse=True)
	return pairs


def _contains_old(text: str, old_forms: list[str]) -> bool:
	return any(o in text for o in old_forms)


def _apply_replacements(text: str, pairs: list[tuple[str, str]]) -> str:
	for old, new in pairs:
		if old in text:
			text = text.replace(old, new)
	return text


def _is_text_candidate(path: Path, data: bytes) -> bool:
	name = path.name.lower()
	if name in {"pyvenv.cfg"} or name.endswith(".pth") or name == "direct_url.json":
		return True
	if name.startswith("activate"):
		return True
	if data.startswith(b"#!"):
		return True
	probe = data[:1024]
	if b"\0" in probe:
		return False
	try:
		data.decode("utf-8")
	except UnicodeDecodeError:
		return False
	return True


def _rewrite_text_file(path: Path, pairs: list[tuple[str, str]], old_forms: list[str]) -> bool:
	"""Rewrite *path* if it contains an old root form. Returns True if changed."""
	try:
		data = path.read_bytes()
	except OSError as exc:
		print(f"error: cannot read {path}: {exc}", file=sys.stderr)
		raise SystemExit(1) from exc
	if not _is_text_candidate(path, data):
		return False
	try:
		text = data.decode("utf-8")
	except UnicodeDecodeError:
		return False
	if not _contains_old(text, old_forms):
		return False
	new_text = _apply_replacements(text, pairs)
	if new_text == text:
		return False
	# newline="" preserves existing \\n / \\r\\n from the decoded bytes.
	path.write_text(new_text, encoding="utf-8", newline="")
	return True


def _iter_site_packages(venv: Path):
	lib = venv / "lib"
	if lib.is_dir():
		yield from lib.glob("python*/site-packages")
	win_site = venv / "Lib" / "site-packages"
	if win_site.is_dir():
		yield win_site


def _collect_text_targets(venv: Path) -> list[Path]:
	targets: list[Path] = []
	for scripts_name in ("bin", "Scripts"):
		scripts = venv / scripts_name
		if not scripts.is_dir():
			continue
		for path in scripts.iterdir():
			if path.is_file() and not path.is_symlink():
				targets.append(path)
	cfg = venv / "pyvenv.cfg"
	if cfg.is_file():
		targets.append(cfg)
	for site in _iter_site_packages(venv):
		targets.extend(sorted(site.glob("*.pth")))
		targets.extend(sorted(site.glob("*.dist-info/direct_url.json")))
	seen: set[Path] = set()
	unique: list[Path] = []
	for path in targets:
		resolved = path.resolve()
		if resolved in seen:
			continue
		seen.add(resolved)
		unique.append(path)
	return unique


def _read_pyvenv_home(venv: Path) -> str | None:
	cfg = venv / "pyvenv.cfg"
	if not cfg.is_file():
		return None
	for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
		if line.startswith("home"):
			_, _, value = line.partition("=")
			return value.strip() or None
	return None


def _old_venv_python_forms(old_root: Path) -> list[str]:
	"""Path forms for the old venv's python.exe (Windows trampoline target)."""
	forms: list[str] = []
	for base in (
		old_root / ".venv" / "Scripts" / "python.exe",
		old_root / ".venv" / "Scripts" / "pythonw.exe",
	):
		for form in _path_variants(base):
			if form not in forms:
				forms.append(form)
	return forms


def _update_windows_trampoline_python_path(exe: Path, new_python: Path):
	"""Set UV_PYTHON_PATH PE resource on a uv trampoline."""
	import ctypes
	from ctypes import wintypes

	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

	BeginUpdateResourceW = kernel32.BeginUpdateResourceW
	BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
	BeginUpdateResourceW.restype = wintypes.HANDLE

	UpdateResourceW = kernel32.UpdateResourceW
	UpdateResourceW.argtypes = [
		wintypes.HANDLE,
		ctypes.c_void_p,
		wintypes.LPCWSTR,
		wintypes.WORD,
		wintypes.LPVOID,
		wintypes.DWORD,
	]
	UpdateResourceW.restype = wintypes.BOOL

	EndUpdateResourceW = kernel32.EndUpdateResourceW
	EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
	EndUpdateResourceW.restype = wintypes.BOOL

	python_bytes = str(new_python).encode("utf-8")
	buf = ctypes.create_string_buffer(python_bytes)
	handle = BeginUpdateResourceW(str(exe), False)
	if not handle:
		err = ctypes.get_last_error()
		print(
			f"error: BeginUpdateResourceW failed for {exe} (winerr={err})",
			file=sys.stderr,
		)
		raise SystemExit(1)

	ok = UpdateResourceW(
		handle,
		ctypes.c_void_p(10),  # RT_RCDATA
		"UV_PYTHON_PATH",
		0,  # language neutral
		buf,
		len(python_bytes),
	)
	if not ok:
		err = ctypes.get_last_error()
		EndUpdateResourceW(handle, True)  # discard
		print(
			f"error: UpdateResourceW failed for {exe} (winerr={err})",
			file=sys.stderr,
		)
		raise SystemExit(1)
	if not EndUpdateResourceW(handle, False):
		err = ctypes.get_last_error()
		print(
			f"error: EndUpdateResourceW failed for {exe} (winerr={err})",
			file=sys.stderr,
		)
		raise SystemExit(1)


def _rewrite_windows_trampolines(
	venv: Path,
	old_root: Path,
	new_root: Path,
) -> int:
	"""Patch Scripts/*.exe trampolines that embed the old venv python path."""
	if sys.platform != "win32":
		return 0
	scripts = venv / "Scripts"
	if not scripts.is_dir():
		return 0

	old_python_forms = _old_venv_python_forms(old_root)
	old_python_bytes = [f.encode("utf-8") for f in old_python_forms]
	new_python = (new_root / ".venv" / "Scripts" / "python.exe").resolve()
	home = _read_pyvenv_home(venv)
	home_bytes = home.encode("utf-8") if home else None

	updated = 0
	for exe in sorted(scripts.glob("*.exe")):
		name = exe.name.lower()
		try:
			data = exe.read_bytes()
		except OSError as exc:
			print(f"error: cannot read {exe}: {exc}", file=sys.stderr)
			raise SystemExit(1) from exc

		embeds_old_venv_python = any(b in data for b in old_python_bytes)
		if name in {"python.exe", "pythonw.exe"}:
			# Leave uv-managed interpreter trampolines alone.
			if home_bytes and home_bytes in data and not embeds_old_venv_python:
				continue
			if not embeds_old_venv_python:
				continue
		elif not embeds_old_venv_python:
			continue

		_update_windows_trampoline_python_path(exe, new_python)
		updated += 1
		print(f"  trampoline: {exe.name}")
	return updated


def rewrite_venv_paths(old_root: Path, new_root: Path) -> dict[str, int]:
	"""Rewrite paths under ``new_root/.venv``. Returns counts of changes."""
	old_root = old_root.resolve()
	new_root = new_root.resolve()
	venv = new_root / ".venv"
	if not venv.is_dir():
		print(f"error: venv not found at {venv}", file=sys.stderr)
		raise SystemExit(1)

	pairs = _build_replacements(old_root, new_root)
	old_forms = [o for o, _ in pairs]
	if not pairs:
		print("error: old and new roots produced no replacements", file=sys.stderr)
		raise SystemExit(1)

	text_changed = 0
	for path in _collect_text_targets(venv):
		if _rewrite_text_file(path, pairs, old_forms):
			text_changed += 1
			print(f"  text: {path.relative_to(venv)}")

	trampolines = _rewrite_windows_trampolines(venv, old_root, new_root)

	leftovers: list[Path] = []
	for path in _collect_text_targets(venv):
		try:
			data = path.read_bytes()
		except OSError:
			continue
		if not _is_text_candidate(path, data):
			continue
		try:
			text = data.decode("utf-8")
		except UnicodeDecodeError:
			continue
		if _contains_old(text, old_forms):
			leftovers.append(path)
	if leftovers:
		print("error: old project path still present after rewrite:", file=sys.stderr)
		for path in leftovers[:20]:
			print(f"  {path}", file=sys.stderr)
		raise SystemExit(1)

	return {"text": text_changed, "trampolines": trampolines}


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--old-root", required=True, type=Path, help="Primary checkout root")
	parser.add_argument("--new-root", required=True, type=Path, help="Worktree root")
	args = parser.parse_args(argv)

	print("rewrite-venv-paths:")
	print(f"  old: {args.old_root.resolve()}")
	print(f"  new: {args.new_root.resolve()}")
	counts = rewrite_venv_paths(args.old_root, args.new_root)
	print(f"  rewritten text files: {counts['text']}")
	if counts["trampolines"]:
		print(f"  updated trampolines: {counts['trampolines']}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
