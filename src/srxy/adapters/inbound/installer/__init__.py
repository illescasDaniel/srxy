"""Desktop install / uninstall wizard (PySide on Linux/macOS; headless CLI for Windows Inno)."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
	from srxy.adapters.inbound.installer.app import run_installer as run_installer


def __getattr__(name: str):
	if name == "run_installer":
		from srxy.adapters.inbound.installer.app import run_installer as impl

		return impl
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["run_installer"]
