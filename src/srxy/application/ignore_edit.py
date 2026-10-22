"""Qt-free helpers for adding/removing ignore rules from picks and result rows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from srxy.domain.ignore_rules import escape_literal


class PathOutsideRootError(ValueError):
	"""Raised when a picked path is not inside the search root."""


@dataclass(frozen=True, slots=True)
class IgnoreChoice:
	kind: str  # "file" | "folder" | "ext" | "this_folder" | "archive"
	pattern: str
	display: str  # name/ext shown in the label


def _escape(name: str) -> str:
	"""`escape_literal` plus `]`, so picked names read unambiguously next to an escaped `[`."""
	return escape_literal(name).replace("]", "\\]")


def _relative_parts(path: Path, root: Path, *, follow_leaf: bool = True) -> tuple[str, ...]:
	"""`follow_leaf=False` keeps the last component unresolved, so a symlink is matched by its own path."""
	try:
		resolved = path.resolve() if follow_leaf else path.parent.resolve() / path.name
		return resolved.relative_to(root.resolve()).parts
	except ValueError as error:
		raise PathOutsideRootError(str(path)) from error


def _pattern_from_parts(parts: tuple[str, ...], *, is_dir: bool) -> str:
	pattern = "/" + "/".join(_escape(part) for part in parts)
	return pattern + "/" if is_dir and parts else pattern


def pattern_for_path(path: Path, root: Path, *, is_dir: bool, follow_leaf: bool = True) -> str:
	"""resolve() both; outside -> PathOutsideRootError; '/a/b' or '/a/b/', parts escaped."""
	parts = _relative_parts(path, root, follow_leaf=follow_leaf)
	pattern = "/" + "/".join(_escape(part) for part in parts)
	return pattern + "/" if is_dir and parts else pattern


def row_ignore_choices(path: Path, root: Path, *, is_dir: bool, archive_path: Path | None) -> list[IgnoreChoice]:
	"""Archive member -> only [archive]; dir result -> [this_folder]; file -> file, folder, ext.

	Row paths are matched by their own path: a symlink leaf is not followed to its target.
	"""
	if archive_path is not None:
		return [
			IgnoreChoice(
				kind="archive",
				pattern=pattern_for_path(archive_path, root, is_dir=False, follow_leaf=False),
				display=archive_path.name,
			)
		]
	if is_dir:
		return [
			IgnoreChoice(
				kind="this_folder",
				pattern=pattern_for_path(path, root, is_dir=True, follow_leaf=False),
				display=path.name,
			)
		]
	parts = _relative_parts(path, root, follow_leaf=False)
	choices = [
		IgnoreChoice(kind="file", pattern=_pattern_from_parts(parts, is_dir=False), display=path.name),
	]
	if len(parts) > 1:
		choices.append(
			IgnoreChoice(kind="folder", pattern=_pattern_from_parts(parts[:-1], is_dir=True), display=parts[-2])
		)
	suffix = path.suffix
	if suffix and suffix != path.name:
		choices.append(IgnoreChoice(kind="ext", pattern="*" + _escape(suffix), display=suffix))
	return choices


def add_ignore_line(text: str, pattern: str) -> tuple[str, bool]:
	"""Return (new_text, added); duplicates are a no-op."""
	lines = text.splitlines()
	if pattern in lines:
		return text, False
	lines.append(pattern)
	return "\n".join(lines), True


def remove_ignore_line(text: str, pattern: str) -> str:
	"""Remove the last exact occurrence only."""
	lines = text.splitlines()
	for index in range(len(lines) - 1, -1, -1):
		if lines[index] == pattern:
			del lines[index]
			break
	else:
		return text
	return "\n".join(lines)
