from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path


_KEYWORDS_PROPERTY = "System.Keywords"
_TAG_LABEL = "Windows tag"


def windows_tags_supported() -> bool:
	if sys.platform != "win32":
		return False
	return importlib.util.find_spec("win32com.propsys") is not None


def windows_tags_writable() -> bool:
	if not windows_tags_supported():
		return False

	import tempfile

	with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
		probe_path = Path(handle.name)
	try:
		write_windows_keywords(probe_path, ["srxy-probe"])
		return "srxy-probe" in _read_windows_keywords(probe_path)
	except OSError:
		return False
	finally:
		probe_path.unlink(missing_ok=True)


def has_windows_tags(path: Path) -> bool:
	return bool(_read_windows_keywords(path))


def iter_windows_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	for line_number, tag in enumerate(_read_windows_keywords(path), start=1):
		yield line_number, f"[{_TAG_LABEL}] {tag}"


def _read_windows_keywords(path: Path) -> list[str]:
	if not windows_tags_supported():
		return []
	try:
		keywords = _read_keywords_via_property_store(path)
	except OSError:
		return []
	return normalize_windows_keywords(keywords)


def _read_keywords_via_property_store(path: Path) -> object:
	import pythoncom
	from win32com.propsys import propsys
	from win32com.shell import shellcon

	pythoncom.CoInitialize()
	try:
		property_key = propsys.PSGetPropertyKeyFromName(_KEYWORDS_PROPERTY)
		store = propsys.SHGetPropertyStoreFromParsingName(
			str(path.resolve()),
			None,
			shellcon.GPS_DEFAULT,
			propsys.IID_IPropertyStore,
		)
		variant = store.GetValue(property_key)
		try:
			return variant.GetValue()
		except AttributeError:
			return None
	except Exception as error:
		raise OSError(str(error)) from error
	finally:
		pythoncom.CoUninitialize()


def write_windows_keywords(path: Path, tags: list[str]) -> None:
	import pythoncom
	from win32com.propsys import propsys
	from win32com.shell import shellcon

	pythoncom.CoInitialize()
	try:
		property_key = propsys.PSGetPropertyKeyFromName(_KEYWORDS_PROPERTY)
		store = propsys.SHGetPropertyStoreFromParsingName(
			str(path.resolve()),
			None,
			shellcon.GPS_READWRITE,
			propsys.IID_IPropertyStore,
		)
		if tags:
			value = propsys.PROPVARIANTType(tags, pythoncom.VT_VECTOR | pythoncom.VT_LPWSTR)
		else:
			value = propsys.PROPVARIANTType(None, pythoncom.VT_EMPTY)
		store.SetValue(property_key, value)
		store.Commit()
	except Exception as error:
		raise OSError(str(error)) from error
	finally:
		pythoncom.CoUninitialize()


def normalize_windows_keywords(value: object) -> list[str]:
	if value is None:
		return []
	if isinstance(value, str):
		text = value.strip()
		return [text] if text else []
	if isinstance(value, list):
		tags: list[str] = []
		for item in value:
			if item is None:
				continue
			text = str(item).strip()
			if text:
				tags.append(text)
		return tags
	return []
