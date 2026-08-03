"""Outbound port: OS desktop integration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DesktopPort(Protocol):
	def open_path(self, path: Path) -> None: ...

	def copy_text(self, text: str) -> None: ...
