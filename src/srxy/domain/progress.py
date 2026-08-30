from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias


ActivityCallback: TypeAlias = Callable[["ActivityUpdate | None"], None]


ACTIVITY_SPINNER_FRAMES = "⠋⠙⠹⠼⠴⠦⠧⠇⠏"


@dataclass(frozen=True, slots=True)
class ActivityUpdate:
	label: str | None
	current: int | None = None
	total: int | None = None

	@property
	def indeterminate(self) -> bool:
		return self.label is not None and not self.determinate

	@property
	def determinate(self) -> bool:
		return self.label is not None and self.current is not None and self.total is not None and self.total > 0


def emit_activity(
	on_activity: ActivityCallback | None,
	label: str,
	*,
	current: int | None = None,
	total: int | None = None,
):
	if on_activity is not None:
		on_activity(ActivityUpdate(label=label, current=current, total=total))


def clear_activity(on_activity: ActivityCallback | None):
	if on_activity is not None:
		on_activity(None)


def concurrent_activity_fan_in(downstream: ActivityCallback) -> ActivityCallback:
	"""Merge per-thread activity updates so concurrent OCR/transcribe can share one status line.

	Each thread owns one slot. ``None`` clears that thread only. Downstream sees the
	most recently updated remaining label, or ``None`` when no slots remain.
	"""
	lock = threading.Lock()
	by_thread: dict[int, ActivityUpdate] = {}

	def _fan_in(update: ActivityUpdate | None):
		tid = threading.get_ident()
		with lock:
			if update is None or update.label is None:
				by_thread.pop(tid, None)
			else:
				by_thread.pop(tid, None)
				by_thread[tid] = update
			if not by_thread:
				downstream(None)
			else:
				downstream(next(reversed(by_thread.values())))

	return _fan_in


def activity_short_label(label: str) -> str:
	if " · " in label:
		return label.split(" · ", 1)[0]
	return label


def format_activity_status(
	activity: ActivityUpdate,
	*,
	spinner_frame: str = ACTIVITY_SPINNER_FRAMES[0],
) -> str:
	body = format_activity_status_body(activity)
	if not body:
		return ""
	if spinner_frame:
		return f"{spinner_frame} {body}"
	return body


def format_activity_status_body(activity: ActivityUpdate) -> str:
	"""Activity status text without the spinner glyph (GUI animates the glyph separately)."""
	if activity.label is None:
		return ""
	task = activity.label
	if activity.determinate and activity.current is not None and activity.total is not None:
		percent = int((activity.current / activity.total) * 100)
		return f"{percent}% {task}"
	return task


def is_generic_searching_activity(activity: ActivityUpdate | None, *, searching_label: str) -> bool:
	"""True when status should yield to determinate Scanning N/M text."""
	return activity is None or activity.label is None or activity.label == searching_label


__all__ = [
	"ACTIVITY_SPINNER_FRAMES",
	"ActivityCallback",
	"ActivityUpdate",
	"activity_short_label",
	"clear_activity",
	"concurrent_activity_fan_in",
	"emit_activity",
	"format_activity_status",
	"format_activity_status_body",
	"is_generic_searching_activity",
]
