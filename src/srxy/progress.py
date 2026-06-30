from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias


ActivityCallback: TypeAlias = Callable[["ActivityUpdate | None"], None]


ACTIVITY_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


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


def activity_short_label(label: str) -> str:
	if " · " in label:
		return label.split(" · ", 1)[0]
	return label


def format_activity_status(
	activity: ActivityUpdate,
	*,
	spinner_frame: str = ACTIVITY_SPINNER_FRAMES[0],
) -> str:
	if activity.label is None:
		return ""
	task = activity.label
	if activity.determinate and activity.current is not None and activity.total is not None:
		percent = int((activity.current / activity.total) * 100)
		return f"{spinner_frame} {percent}% {task}"
	return f"{spinner_frame} {task}"


__all__ = [
	"ACTIVITY_SPINNER_FRAMES",
	"ActivityCallback",
	"ActivityUpdate",
	"activity_short_label",
	"clear_activity",
	"emit_activity",
	"format_activity_status",
]
