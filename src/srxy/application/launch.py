"""Launch-mode selection for GUI / TUI / plain CLI."""

from __future__ import annotations

import argparse
import os
import sys


_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def _ci_forced() -> bool:
	return os.environ.get("CI", "").strip().lower() in _TRUTHY_ENV_VALUES


def _plain_cli_forced(args: argparse.Namespace) -> bool:
	if getattr(args, "cli", False):
		return True
	if args.json or args.format == "flat" or args.output is not None:
		return True
	if _ci_forced():
		return True
	return False


def _has_tty() -> bool:
	return sys.stdout.isatty() and sys.stderr.isatty()


def gui_display_available() -> bool:
	"""Return True when a graphical session is likely available."""
	system = sys.platform
	if system == "darwin":
		return True
	if system == "win32":
		return True
	display = os.environ.get("DISPLAY", "").strip()
	wayland = os.environ.get("WAYLAND_DISPLAY", "").strip()
	return bool(display or wayland)


def gui_importable() -> bool:
	try:
		from importlib import import_module

		import_module("PySide6.QtGui")
	except Exception:
		return False
	return True


def should_use_cli(args: argparse.Namespace) -> bool:
	return _plain_cli_forced(args) or not _has_tty()


def should_use_gui(args: argparse.Namespace) -> bool:
	if getattr(args, "tui", False):
		return False
	if _plain_cli_forced(args):
		return False
	if not gui_display_available():
		return False
	if not gui_importable():
		return False
	return True


def should_use_tui(args: argparse.Namespace) -> bool:
	"""TUI when forced with --tui, or as fallthrough when GUI is unavailable."""
	if _plain_cli_forced(args):
		return False
	if not _has_tty():
		return False
	if getattr(args, "tui", False):
		return True
	# Fallthrough when GUI cannot start
	return not should_use_gui(args)
