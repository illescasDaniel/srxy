from __future__ import annotations

import importlib.util
import sys
import threading
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path


_SEARCHABLE_PROPERTIES: dict[str, str] = {
	"System.Keywords": "Windows tag",
	"System.ApplicationName": "Program name",
	"System.Document.LastAuthor": "Last saved by",
	"System.Author": "Author",
	"System.Title": "Title",
	"System.Subject": "Subject",
	"System.Comment": "Comment",
	"System.Company": "Company",
	"System.Category": "Category",
	"System.Document.RevisionNumber": "Revision number",
}
_KEYWORDS_PROPERTY = "System.Keywords"
# COM was already initialized on this thread with a different apartment model.
_RPC_E_CHANGED_MODE = -2147417850
# CoInitializeEx returns S_FALSE when COM is already initialized compatibly.
_COM_ALREADY_INITIALIZED = 1

_COM_STATE = threading.local()


def windows_tags_supported() -> bool:
	if sys.platform != "win32":
		return False
	return importlib.util.find_spec("win32com.propsys") is not None


windows_metadata_supported = windows_tags_supported


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


def has_windows_searchable_metadata(path: Path) -> bool:
	return bool(_read_searchable_property_entries(path))


def iter_windows_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	for line_number, (label, value) in enumerate(_read_searchable_property_entries(path), start=1):
		yield line_number, f"[{label}] {value}"


def _read_windows_keywords(path: Path) -> list[str]:
	if not windows_tags_supported():
		return []
	try:
		keywords = _read_property_value(path, _KEYWORDS_PROPERTY)
	except OSError:
		return []
	return normalize_windows_keywords(keywords)


def _read_searchable_property_entries(path: Path) -> list[tuple[str, str]]:
	if not windows_metadata_supported():
		return []
	try:
		store = _open_property_store(path)
	except OSError:
		return []

	entries: list[tuple[str, str]] = []
	for property_name, label in _SEARCHABLE_PROPERTIES.items():
		try:
			raw_value = _read_property_value_from_store(store, property_name)
		except OSError:
			continue
		if property_name == _KEYWORDS_PROPERTY:
			for value in normalize_windows_keywords(raw_value):
				entries.append((label, value))
			continue
		for value in _format_property_values(raw_value):
			entries.append((label, value))
	return entries


def reset_thread_com_state_for_tests():
	"""Clear per-thread COM init flags. For unit tests only."""
	for attr in ("ready", "failed"):
		if hasattr(_COM_STATE, attr):
			delattr(_COM_STATE, attr)


def _ensure_com_initialized():
	if getattr(_COM_STATE, "ready", False):
		return
	if getattr(_COM_STATE, "failed", False):
		raise OSError("COM is not available on this thread")

	import pythoncom

	try:
		pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
	except pythoncom.com_error as error:
		hresult = error.hresult
		if hresult in (_COM_ALREADY_INITIALIZED, _RPC_E_CHANGED_MODE):
			_COM_STATE.ready = True
			return
		_COM_STATE.failed = True
		raise OSError(str(error)) from error
	_COM_STATE.ready = True


def _open_property_store(path: Path, *, readwrite: bool = False):
	import pythoncom
	from win32com.propsys import propsys
	from win32com.shell import shellcon

	_ensure_com_initialized()
	try:
		flags = shellcon.GPS_READWRITE if readwrite else shellcon.GPS_DEFAULT
		return propsys.SHGetPropertyStoreFromParsingName(
			str(path.resolve()),
			None,
			flags,
			propsys.IID_IPropertyStore,
		)
	except pythoncom.com_error as error:
		raise OSError(str(error)) from error
	except Exception as error:
		raise OSError(str(error)) from error


def _read_property_value(path: Path, property_name: str) -> object:
	store = _open_property_store(path)
	return _read_property_value_from_store(store, property_name)


def _read_property_value_from_store(store: object, property_name: str) -> object:
	from win32com.propsys import propsys

	try:
		property_key = propsys.PSGetPropertyKeyFromName(property_name)
		variant = store.GetValue(property_key)
		try:
			return variant.GetValue()
		except AttributeError:
			return None
	except Exception as error:
		raise OSError(str(error)) from error


def write_windows_keywords(path: Path, tags: list[str]) -> None:
	import pythoncom
	from win32com.propsys import propsys

	_ensure_com_initialized()
	try:
		property_key = propsys.PSGetPropertyKeyFromName(_KEYWORDS_PROPERTY)
		store = _open_property_store(path, readwrite=True)
		if tags:
			value = propsys.PROPVARIANTType(tags, pythoncom.VT_VECTOR | pythoncom.VT_LPWSTR)
		else:
			value = propsys.PROPVARIANTType(None, pythoncom.VT_EMPTY)
		store.SetValue(property_key, value)
		store.Commit()
	except pythoncom.com_error as error:
		raise OSError(str(error)) from error
	except Exception as error:
		raise OSError(str(error)) from error


def normalize_windows_keywords(value: object) -> list[str]:
	if value is None:
		return []
	if isinstance(value, str):
		text = value.strip()
		if not text:
			return []
		if ";" in text:
			return [part.strip() for part in text.split(";") if part.strip()]
		return [text]
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


def _format_property_values(value: object) -> list[str]:
	if value is None:
		return []
	if isinstance(value, str):
		text = value.strip()
		return [text] if text else []
	if isinstance(value, datetime):
		return [value.isoformat(sep=" ", timespec="seconds")]
	if isinstance(value, date):
		return [value.isoformat()]
	if isinstance(value, (int, float, bool)):
		return [str(value)]
	if isinstance(value, list):
		formatted: list[str] = []
		for item in value:
			formatted.extend(_format_property_values(item))
		return formatted
	text = str(value).strip()
	return [text] if text else []
