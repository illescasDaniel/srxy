"""Pure initial search-root selection for command and app GUI launches."""

from __future__ import annotations

import os


def initial_gui_search_path(
	raw: str | None,
	*,
	app_launch: bool,
	cwd: str | None,
	home: str,
) -> str:
	"""Choose the startup default without inspecting the filesystem."""
	if raw is None:
		return home if app_launch or cwd is None else cwd
	if not raw:
		return raw
	if raw == "~":
		return home
	if raw.startswith(("~/", "~" + os.sep)):
		raw = home.rstrip(os.sep + (os.altsep or "")) + raw[1:]
	if raw.startswith("~") or os.path.isabs(raw) or cwd is None:
		return raw
	return cwd if raw == "." else os.path.join(cwd, raw)
