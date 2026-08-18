"""OS desktop adapter — open files and clipboard via system tools."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def open_path(path: Path):
	"""Open ``path`` with the OS default application (archive-aware)."""
	from srxy.adapters.outbound.archive.archive_search import split_archive_member_path

	archive_path, member = split_archive_member_path(path)
	open_target = archive_path if member is not None else path
	system = platform.system()
	if system == "Darwin":
		subprocess.run(["open", str(open_target)], check=False)  # noqa: S603, S607
	elif system == "Windows":
		os.startfile(str(open_target))  # type: ignore[attr-defined]  # noqa: S606
	else:
		subprocess.run(["xdg-open", str(open_target)], check=False)  # noqa: S603, S607


def reveal_path(path: Path):
	"""Reveal ``path`` in the OS file manager (select a file, open a directory)."""
	from srxy.adapters.outbound.archive.archive_search import split_archive_member_path

	archive_path, member = split_archive_member_path(path)
	target = archive_path if member is not None else path
	system = platform.system()
	if system == "Darwin":
		if target.is_dir():
			subprocess.run(["open", str(target)], check=False)  # noqa: S603, S607
		else:
			subprocess.run(["open", "-R", str(target)], check=False)  # noqa: S603, S607
	elif system == "Windows":
		if target.is_dir():
			os.startfile(str(target))  # type: ignore[attr-defined]  # noqa: S606
		else:
			subprocess.run(["explorer", f"/select,{target}"], check=False)  # noqa: S603, S607
	else:
		open_target = target if target.is_dir() else target.parent
		subprocess.run(["xdg-open", str(open_target)], check=False)  # noqa: S603, S607


def copy_text(text: str):
	"""Copy plain text to the system clipboard when possible."""
	system = platform.system()
	if system == "Darwin":
		pbcopy = shutil.which("pbcopy")
		if pbcopy is not None:
			subprocess.run(  # noqa: S603
				[pbcopy],
				input=text.encode("utf-8"),
				check=True,
				timeout=3,
			)
			return
	if system == "Windows":
		clip = shutil.which("clip")
		if clip is not None:
			subprocess.run(  # noqa: S603
				[clip],
				input=text.encode("utf-16le"),
				check=True,
				timeout=3,
			)
			return
	xclip = shutil.which("xclip")
	if xclip is not None:
		subprocess.run(  # noqa: S603
			[xclip, "-selection", "clipboard"],
			input=text.encode("utf-8"),
			check=True,
			timeout=3,
		)
		return
	xsel = shutil.which("xsel")
	if xsel is not None:
		subprocess.run(  # noqa: S603
			[xsel, "--clipboard", "--input"],
			input=text.encode("utf-8"),
			check=True,
			timeout=3,
		)
		return
	raise OSError("no clipboard utility available")


class OsDesktopAdapter:
	"""DesktopPort using OS openers and clipboard CLIs."""

	def open_path(self, path: Path):
		open_path(path)

	def reveal_path(self, path: Path):
		reveal_path(path)

	def copy_text(self, text: str):
		copy_text(text)


# Back-compat alias used by earlier bootstrap wiring.
DesktopAdapter = OsDesktopAdapter
