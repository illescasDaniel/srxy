"""PySide6 + QML GUI inbound adapter (stub until fully wired)."""

from __future__ import annotations

import argparse


def run_gui(args: argparse.Namespace, *, auto_start: bool = False) -> int:
	from srxy.adapters.inbound.gui.app import run_gui as _run

	return _run(args, auto_start=auto_start)


__all__ = ["run_gui"]
