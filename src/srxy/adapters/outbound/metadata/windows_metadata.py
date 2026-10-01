from __future__ import annotations

import contextlib
import importlib.util
import json
import subprocess
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
	try:
		return importlib.util.find_spec("win32com.propsys") is not None
	except ModuleNotFoundError:
		# Parent package ``win32com`` missing: find_spec can raise on some Pythons.
		return False


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
	# A malformed/unsupported file (e.g. a corrupt JPEG) can make the Windows
	# Property Store / shell property handler raise a native SEH fault (observed:
	# ``0xc0000002`` STATUS_NOT_IMPLEMENTED) instead of a catchable COM error.
	# That crashes the whole process, bypassing this module's ``except OSError``
	# guards. On real Windows, run the read in a short-lived, reusable worker
	# subprocess so a native fault only kills that child; a dead/unresponsive
	# child is treated the same as ``except OSError: return []``.
	if sys.platform == "win32":
		return _read_searchable_property_entries_isolated(path)
	return _read_searchable_property_entries_direct(path)


def _read_searchable_property_entries_direct(path: Path) -> list[tuple[str, str]]:
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


_ISOLATED_WORKER_LOCK = threading.Lock()
_ISOLATED_WORKER_TIMEOUT_SECONDS = 5.0
_isolated_worker_process: subprocess.Popen[str] | None = None


def _isolated_worker_command() -> list[str]:
	return [sys.executable, "-u", "-m", "srxy.adapters.outbound.metadata.windows_metadata_worker"]


def _spawn_isolated_worker() -> subprocess.Popen[str]:
	creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
	return subprocess.Popen(  # noqa: S603
		_isolated_worker_command(),
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.DEVNULL,
		text=True,
		bufsize=1,
		creationflags=creationflags,
	)


def _terminate_isolated_worker():
	global _isolated_worker_process
	process = _isolated_worker_process
	_isolated_worker_process = None
	if process is None:
		return
	with contextlib.suppress(Exception):
		process.kill()
	with contextlib.suppress(Exception):
		process.wait(timeout=1)


def reset_isolated_worker_for_tests():
	"""Kill and drop any live isolated worker subprocess. For unit tests only."""
	with _ISOLATED_WORKER_LOCK:
		_terminate_isolated_worker()


def _readline_with_timeout(stream, timeout: float) -> str | None:
	"""Read one line, returning ``None`` if nothing arrives within ``timeout``.

	A hung Property Store call (rather than a hard crash) must not block the
	search worker forever, so the read happens on a daemon thread we can give
	up on without joining it.
	"""
	box: list[str] = []

	def _read():
		try:
			box.append(stream.readline())
		except (OSError, ValueError):
			box.append("")

	reader = threading.Thread(target=_read, daemon=True)
	reader.start()
	reader.join(timeout)
	if reader.is_alive():
		return None
	return box[0] if box else ""


def _read_searchable_property_entries_isolated(path: Path) -> list[tuple[str, str]]:
	global _isolated_worker_process
	with _ISOLATED_WORKER_LOCK:
		try:
			if _isolated_worker_process is None or _isolated_worker_process.poll() is not None:
				_isolated_worker_process = _spawn_isolated_worker()
			worker = _isolated_worker_process
			if worker.stdin is None or worker.stdout is None:
				raise OSError("isolated Property Store worker missing stdio pipes")
			worker.stdin.write(json.dumps({"path": str(path)}) + "\n")
			worker.stdin.flush()
			line = _readline_with_timeout(worker.stdout, _ISOLATED_WORKER_TIMEOUT_SECONDS)
		except (OSError, ValueError):
			line = ""

		if not line:
			# The worker died (native fault) or hung/produced nothing. Drop it so
			# the next call respawns a clean one, and fail soft for this file.
			_terminate_isolated_worker()
			return []

		try:
			payload = json.loads(line)
		except ValueError:
			return []
		entries = payload.get("entries") if isinstance(payload, dict) else None
		if not isinstance(entries, list):
			return []
		return [
			(entry[0], entry[1])
			for entry in entries
			if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str) and isinstance(entry[1], str)
		]


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
