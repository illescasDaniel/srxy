"""Cooperative install cancellation (cancel-file protocol)."""

from __future__ import annotations

import os
from pathlib import Path


class InstallCancelledError(RuntimeError):
	"""Raised when the user cancels a running install via the cancel-file protocol."""


def effective_cancel_file(cancel_file: str | None) -> str | None:
	raw = (cancel_file or os.environ.get("SRXY_INSTALLER_CANCEL_FILE", "")).strip()
	return raw or None


def cancel_requested(cancel_file: str | None) -> bool:
	path = effective_cancel_file(cancel_file)
	return bool(path and Path(path).expanduser().is_file())


def raise_if_cancelled(cancel_file: str | None, message: str = "cancelled"):
	if cancel_requested(cancel_file):
		raise InstallCancelledError(message)


__all__ = [
	"InstallCancelledError",
	"cancel_requested",
	"effective_cancel_file",
	"raise_if_cancelled",
]
