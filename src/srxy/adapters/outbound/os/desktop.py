"""OS desktop adapter — open files and clipboard."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def open_path(path: Path) -> None:
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


def copy_text(text: str) -> None:
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


class DesktopAdapter:
	def open_path(self, path: Path):
		open_path(path)

	def copy_text(self, text: str):
		copy_text(text)
