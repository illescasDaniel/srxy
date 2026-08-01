"""Textual TUI desktop adapter (clipboard with toolkit fallback)."""

from __future__ import annotations

import platform
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from srxy.adapters.outbound.os.desktop import open_path


class TextualDesktopAdapter:
	"""DesktopPort for the TUI — Darwin pbcopy, then Textual/OS fallback."""

	def __init__(self, *, copy_fallback: Callable[[str], None] | None = None):
		self._copy_fallback = copy_fallback

	def open_path(self, path: Path):
		open_path(path)

	def copy_text(self, text: str):
		if platform.system() == "Darwin":
			pbcopy = shutil.which("pbcopy")
			if pbcopy is not None:
				try:
					subprocess.run(  # noqa: S603
						[pbcopy],
						input=text.encode("utf-8"),
						check=True,
						timeout=3,
					)
					return
				except (OSError, subprocess.SubprocessError):
					pass
		if self._copy_fallback is not None:
			self._copy_fallback(text)
			return
		from srxy.adapters.outbound.os.desktop import copy_text as os_copy_text

		os_copy_text(text)
