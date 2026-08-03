"""One-click online installer (localhost browser UI; no PySide wizard)."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
	from srxy.adapters.inbound.installer_online.server import run_online_installer as run_online_installer


def __getattr__(name: str):
	if name == "run_online_installer":
		from srxy.adapters.inbound.installer_online.server import run_online_installer as impl

		return impl
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["run_online_installer"]
