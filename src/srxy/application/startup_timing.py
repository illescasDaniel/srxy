"""Opt-in GUI/CLI cold-start timing marks (``SRXY_STARTUP_TIMING=1``)."""

from __future__ import annotations

import os
import sys
import time


_TRUTHY = frozenset({"1", "true", "yes", "on"})

_t0: float | None = None
_last: float | None = None


def enabled() -> bool:
	return os.environ.get("SRXY_STARTUP_TIMING", "").strip().lower() in _TRUTHY


def exit_after_qml() -> bool:
	"""When set with timing, ``run_gui`` quits after ``qml_loaded`` (benchmark only)."""
	return os.environ.get("SRXY_STARTUP_EXIT", "").strip().lower() in _TRUTHY


def begin() -> float:
	"""Record process-relative start; safe to call more than once (keeps first)."""
	global _t0, _last
	now = time.perf_counter()
	if _t0 is None:
		_t0 = now
		_last = now
	return _t0


def mark(name: str):
	"""Print ``[startup] name +XmXs (Δ …)`` to stderr when timing is enabled."""
	if not enabled():
		return
	global _last
	now = time.perf_counter()
	start = begin()
	delta = now - (_last if _last is not None else start)
	total = now - start
	_last = now
	print(f"[startup] {name} +{total:.3f}s (Δ {delta:.3f}s)", file=sys.stderr, flush=True)


__all__ = ["begin", "enabled", "exit_after_qml", "mark"]
