from __future__ import annotations

import ctypes
import ctypes.util
import os
import plistlib
import sys
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
_XATTR_NOFOLLOW = 0x1
_darwin_libc: ctypes.CDLL | None = None


def _darwin_lib() -> ctypes.CDLL | None:
	global _darwin_libc
	if sys.platform != "darwin":
		return None
	if _darwin_libc is not None:
		return _darwin_libc
	libc_path = ctypes.util.find_library("c")
	if libc_path is None:
		return None
	libc = ctypes.CDLL(libc_path, use_errno=True)
	libc.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
	libc.listxattr.restype = ctypes.c_ssize_t
	libc.getxattr.argtypes = [
		ctypes.c_char_p,
		ctypes.c_char_p,
		ctypes.c_void_p,
		ctypes.c_size_t,
		ctypes.c_uint32,
		ctypes.c_int,
	]
	libc.getxattr.restype = ctypes.c_ssize_t
	libc.setxattr.argtypes = [
		ctypes.c_char_p,
		ctypes.c_char_p,
		ctypes.c_void_p,
		ctypes.c_size_t,
		ctypes.c_uint32,
		ctypes.c_int,
	]
	libc.setxattr.restype = ctypes.c_int
	libc.removexattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
	libc.removexattr.restype = ctypes.c_int
	_darwin_libc = libc
	return _darwin_libc


def _uses_darwin_xattr() -> bool:
	return sys.platform == "darwin" and not hasattr(os, "listxattr") and _darwin_lib() is not None


def _xattr_options(follow_symlinks: bool) -> int:
	return 0 if follow_symlinks else _XATTR_NOFOLLOW


def _encode_path(path: str | bytes | os.PathLike[str]) -> bytes:
	return os.fsencode(path)


def _raise_oserror() -> None:
	errno = ctypes.get_errno()
	raise OSError(errno, os.strerror(errno))


def _darwin_listxattr(path: str | bytes | os.PathLike[str], *, follow_symlinks: bool = True) -> list[str]:
	libc = _darwin_lib()
	if libc is None:
		raise OSError("extended attributes are not supported on this platform")
	encoded = _encode_path(path)
	options = _xattr_options(follow_symlinks)
	size = libc.listxattr(encoded, None, 0, options)
	if size < 0:
		_raise_oserror()
	if size == 0:
		return []
	buf = ctypes.create_string_buffer(size)
	size = libc.listxattr(encoded, buf, size, options)
	if size < 0:
		_raise_oserror()
	return [name.decode("utf-8") for name in buf.raw[:size].split(b"\x00") if name]


def _darwin_getxattr(
	path: str | bytes | os.PathLike[str],
	name: str,
	*,
	follow_symlinks: bool = True,
) -> bytes:
	libc = _darwin_lib()
	if libc is None:
		raise OSError("extended attributes are not supported on this platform")
	encoded = _encode_path(path)
	encoded_name = name.encode("utf-8")
	options = _xattr_options(follow_symlinks)
	size = libc.getxattr(encoded, encoded_name, None, 0, 0, options)
	if size < 0:
		_raise_oserror()
	if size == 0:
		return b""
	buf = ctypes.create_string_buffer(size)
	size = libc.getxattr(encoded, encoded_name, buf, size, 0, options)
	if size < 0:
		_raise_oserror()
	return buf.raw[:size]


def _darwin_setxattr(
	path: str | bytes | os.PathLike[str],
	name: str,
	value: bytes,
	*,
	follow_symlinks: bool = True,
) -> None:
	libc = _darwin_lib()
	if libc is None:
		raise OSError("extended attributes are not supported on this platform")
	encoded = _encode_path(path)
	encoded_name = name.encode("utf-8")
	options = _xattr_options(follow_symlinks)
	if libc.setxattr(encoded, encoded_name, value, len(value), 0, options) != 0:
		_raise_oserror()


def _darwin_removexattr(path: str | bytes | os.PathLike[str], name: str, *, follow_symlinks: bool = True) -> None:
	libc = _darwin_lib()
	if libc is None:
		raise OSError("extended attributes are not supported on this platform")
	encoded = _encode_path(path)
	encoded_name = name.encode("utf-8")
	options = _xattr_options(follow_symlinks)
	if libc.removexattr(encoded, encoded_name, options) != 0:
		_raise_oserror()


def _listxattr(path: str | bytes | os.PathLike[str], *, follow_symlinks: bool = True) -> list[str]:
	if hasattr(os, "listxattr"):
		return os.listxattr(path, follow_symlinks=follow_symlinks)
	if _uses_darwin_xattr():
		return _darwin_listxattr(path, follow_symlinks=follow_symlinks)
	raise OSError("extended attributes are not supported on this platform")


def _getxattr(path: str | bytes | os.PathLike[str], name: str, *, follow_symlinks: bool = True) -> bytes:
	if hasattr(os, "getxattr"):
		return os.getxattr(path, name, follow_symlinks=follow_symlinks)
	if _uses_darwin_xattr():
		return _darwin_getxattr(path, name, follow_symlinks=follow_symlinks)
	raise OSError("extended attributes are not supported on this platform")


def _setxattr(
	path: str | bytes | os.PathLike[str],
	name: str,
	value: bytes,
	*,
	follow_symlinks: bool = True,
) -> None:
	if hasattr(os, "setxattr"):
		os.setxattr(path, name, value, follow_symlinks=follow_symlinks)
		return
	if _uses_darwin_xattr():
		_darwin_setxattr(path, name, value, follow_symlinks=follow_symlinks)
		return
	raise OSError("extended attributes are not supported on this platform")


def _removexattr(path: str | bytes | os.PathLike[str], name: str, *, follow_symlinks: bool = True) -> None:
	if hasattr(os, "removexattr"):
		os.removexattr(path, name, follow_symlinks=follow_symlinks)
		return
	if _uses_darwin_xattr():
		_darwin_removexattr(path, name, follow_symlinks=follow_symlinks)
		return
	raise OSError("extended attributes are not supported on this platform")


def set_xattr(path: str | bytes | os.PathLike[str], name: str, value: bytes, *, follow_symlinks: bool = True) -> None:
	_setxattr(path, name, value, follow_symlinks=follow_symlinks)


def xattr_supported() -> bool:
	if hasattr(os, "listxattr") and hasattr(os, "getxattr"):
		return True
	return _uses_darwin_xattr()


def finder_tag_xattr_writable() -> bool:
	if not xattr_supported():
		return False

	with tempfile.NamedTemporaryFile(delete=False) as handle:
		probe_path = handle.name
	try:
		_setxattr(probe_path, _FINDER_TAG_ATTR, b"\x00", follow_symlinks=False)
		_removexattr(probe_path, _FINDER_TAG_ATTR, follow_symlinks=False)
		return True
	except OSError:
		return False
	finally:
		os.unlink(probe_path)


def has_searchable_xattrs(path: Path) -> bool:
	if not xattr_supported():
		return False
	try:
		names = _listxattr(path, follow_symlinks=False)
	except OSError:
		return False
	return any(name in _SEARCHABLE_XATTRS for name in names)


def iter_xattr_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	if not xattr_supported():
		return

	try:
		names = _listxattr(path, follow_symlinks=False)
	except OSError:
		return

	line_number = 0
	for name in sorted(names):
		label = _SEARCHABLE_XATTRS.get(name)
		if label is None:
			continue
		try:
			raw = _getxattr(path, name, follow_symlinks=False)
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
	text = _decode_xattr_text(raw)
	if not text:
		return []
	return [text]


def _decode_xattr_text(raw: bytes) -> str:
	if raw.startswith(b"bplist00"):
		try:
			parsed = plistlib.loads(raw)
		except (plistlib.InvalidFileException, ValueError, TypeError, OverflowError):
			return ""
		if isinstance(parsed, str):
			return parsed.strip()
		return ""
	try:
		return raw.decode("utf-8").strip()
	except UnicodeDecodeError:
		return ""


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
