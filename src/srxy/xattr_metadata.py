from __future__ import annotations

import os
import plistlib
import tempfile
from collections.abc import Iterator
from pathlib import Path


_XDG_TAG_ATTR = "user.xdg.tags"
_DOLPHIN_TAG_ATTR = "user.dolphin.tags"
_FINDER_TAG_ATTR = "com.apple.metadata:_kMDItemUserTags"
_XDG_COMMENT_ATTR = "user.xdg.comment"
_FINDER_COMMENT_ATTR = "com.apple.metadata:kMDItemFinderComment"
_COMMENT_ATTR = "com.apple.metadata:kMDItemComment"
_TAG_STYLE_XATTRS = frozenset({_XDG_TAG_ATTR, _DOLPHIN_TAG_ATTR, _FINDER_TAG_ATTR})
_SEARCHABLE_XATTRS: dict[str, str] = {
	_XDG_TAG_ATTR: "XDG tag",
	_DOLPHIN_TAG_ATTR: "Dolphin tag",
	_FINDER_TAG_ATTR: "Finder tag",
	_XDG_COMMENT_ATTR: "XDG comment",
	_FINDER_COMMENT_ATTR: "Finder comment",
	_COMMENT_ATTR: "Comment",
}


def xattr_supported() -> bool:
	return hasattr(os, "listxattr") and hasattr(os, "getxattr")


def finder_tag_xattr_writable() -> bool:
	if not xattr_supported() or not hasattr(os, "setxattr") or not hasattr(os, "removexattr"):
		return False

	with tempfile.NamedTemporaryFile(delete=False) as handle:
		probe_path = handle.name
	try:
		os.setxattr(probe_path, _FINDER_TAG_ATTR, b"\x00", follow_symlinks=False)
		os.removexattr(probe_path, _FINDER_TAG_ATTR, follow_symlinks=False)
		return True
	except OSError:
		return False
	finally:
		os.unlink(probe_path)


def has_searchable_xattrs(path: Path) -> bool:
	if not xattr_supported():
		return False
	try:
		names = os.listxattr(path, follow_symlinks=False)
	except OSError:
		return False
	return any(name in _SEARCHABLE_XATTRS for name in names)


def iter_xattr_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	if not xattr_supported():
		return

	try:
		names = os.listxattr(path, follow_symlinks=False)
	except OSError:
		return

	line_number = 0
	for name in sorted(names):
		label = _SEARCHABLE_XATTRS.get(name)
		if label is None:
			continue
		try:
			raw = os.getxattr(path, name, follow_symlinks=False)
		except OSError:
			continue
		if name == _FINDER_TAG_ATTR:
			values = _parse_finder_tags(raw)
		elif name in _TAG_STYLE_XATTRS:
			values = _parse_text_tags(raw)
		else:
			values = _parse_text_comment(raw)
		for value in values:
			line_number += 1
			yield line_number, f"[{label}] {value}"


def _parse_text_comment(raw: bytes) -> list[str]:
	try:
		text = raw.decode("utf-8").strip()
	except UnicodeDecodeError:
		return []
	if not text:
		return []
	return [text]


def _parse_text_tags(raw: bytes) -> list[str]:
	try:
		text = raw.decode("utf-8").strip()
	except UnicodeDecodeError:
		return []
	if not text:
		return []
	return _split_tag_values(text)


def _parse_finder_tags(raw: bytes) -> list[str]:
	try:
		parsed = plistlib.loads(raw)
	except (plistlib.InvalidFileException, ValueError, TypeError, OverflowError):
		return []
	if not isinstance(parsed, list):
		return []
	tags: list[str] = []
	for item in parsed:
		if not isinstance(item, str):
			continue
		tag = _clean_finder_tag(item)
		if tag:
			tags.append(tag)
	return tags


def _clean_finder_tag(tag: str) -> str:
	return tag.split("\n", 1)[0].strip()


def _split_tag_values(text: str) -> list[str]:
	return [part.strip() for part in text.split(",") if part.strip()]
