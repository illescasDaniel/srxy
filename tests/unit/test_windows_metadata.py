from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.windows_metadata import (
	_ensure_com_initialized,
	_read_windows_keywords,
	has_windows_tags,
	iter_windows_metadata_lines,
	normalize_windows_keywords,
	reset_thread_com_state_for_tests,
	windows_tags_supported,
)


_RPC_E_CHANGED_MODE = -2147417850


pytestmark = pytest.mark.unit


class FakeComError(Exception):
	def __init__(self, hresult: int, message: str = "com error"):
		self.hresult = hresult
		super().__init__(message)


def test_given_string_keyword_when_normalizing_then_returns_single_item():
	# when
	tags = normalize_windows_keywords("cursor")

	# then
	assert tags == ["cursor"]


def test_given_keyword_list_when_normalizing_then_returns_strings():
	# when
	tags = normalize_windows_keywords(["cursor", " quarterly ", None, ""])

	# then
	assert tags == ["cursor", "quarterly"]


def test_given_none_when_normalizing_then_returns_empty_list():
	# then
	assert normalize_windows_keywords(None) == []


def test_given_keyword_list_when_iterating_windows_lines_then_yields_tags(tmp_path: Path):
	# given
	file_path = tmp_path / "clip.mp4"

	# when
	with patch("srxy.windows_metadata._read_windows_keywords", return_value=["cursor", "quarterly"]):
		lines = list(iter_windows_metadata_lines(file_path))

	# then
	assert lines == [(1, "[Windows tag] cursor"), (2, "[Windows tag] quarterly")]


def test_given_property_store_error_when_reading_keywords_then_returns_empty(tmp_path: Path):
	# given
	file_path = tmp_path / "clip.mp4"

	# when
	with (
		patch("srxy.windows_metadata.windows_tags_supported", return_value=True),
		patch("srxy.windows_metadata._read_keywords_via_property_store", side_effect=OSError("access denied")),
	):
		tags = list(iter_windows_metadata_lines(file_path))

	# then
	assert tags == []


def test_given_non_windows_platform_when_checking_support_then_returns_false():
	# when
	with patch("srxy.windows_metadata.sys.platform", "linux"):
		supported = windows_tags_supported()

	# then
	assert supported is False


def test_given_rpc_e_changed_mode_when_ensuring_com_then_marks_thread_ready():
	# given
	reset_thread_com_state_for_tests()
	fake_pythoncom = MagicMock()
	fake_pythoncom.COINIT_APARTMENTTHREADED = 2
	fake_pythoncom.CoInitializeEx.side_effect = FakeComError(_RPC_E_CHANGED_MODE, "WinError 10106")
	fake_pythoncom.com_error = FakeComError

	# when
	with patch.dict("sys.modules", {"pythoncom": fake_pythoncom}):
		_ensure_com_initialized()

	# then
	fake_pythoncom.CoInitializeEx.assert_called_once()
	_ensure_com_initialized()
	fake_pythoncom.CoInitializeEx.assert_called_once()


def test_given_winerror_10106_when_reading_keywords_then_returns_empty(tmp_path: Path):
	# given
	file_path = tmp_path / "clip.mp4"
	file_path.write_bytes(b"x")

	# when
	with (
		patch("srxy.windows_metadata.windows_tags_supported", return_value=True),
		patch(
			"srxy.windows_metadata._read_keywords_via_property_store",
			side_effect=OSError("[WinError 10106] The requested service provider could not be loaded or initialized"),
		),
	):
		tags = _read_windows_keywords(file_path)

	# then
	assert tags == []
	assert has_windows_tags(file_path) is False


def test_given_same_thread_when_reading_keywords_twice_then_initializes_com_once(tmp_path: Path):
	# given
	reset_thread_com_state_for_tests()
	file_path = tmp_path / "clip.mp4"
	file_path.write_bytes(b"x")
	fake_pythoncom = MagicMock()
	fake_pythoncom.COINIT_APARTMENTTHREADED = 2
	fake_pythoncom.com_error = FakeComError
	fake_propsys = MagicMock()
	fake_propsys.PSGetPropertyKeyFromName.return_value = "property-key"
	fake_propsys.IID_IPropertyStore = "store-id"
	fake_store = MagicMock()
	fake_variant = MagicMock()
	fake_variant.GetValue.return_value = ["cursor"]
	fake_store.GetValue.return_value = fake_variant
	fake_propsys.SHGetPropertyStoreFromParsingName.return_value = fake_store
	fake_shellcon = MagicMock()
	fake_shellcon.GPS_DEFAULT = 0

	# when
	with (
		patch("srxy.windows_metadata.windows_tags_supported", return_value=True),
		patch.dict(
			"sys.modules",
			{
				"pythoncom": fake_pythoncom,
				"win32com.propsys": MagicMock(propsys=fake_propsys),
				"win32com.shell": MagicMock(shellcon=fake_shellcon),
			},
		),
	):
		first = _read_windows_keywords(file_path)
		second = _read_windows_keywords(file_path)

	# then
	assert first == ["cursor"]
	assert second == ["cursor"]
	fake_pythoncom.CoInitializeEx.assert_called_once()


def test_given_worker_thread_when_reading_keywords_then_initializes_com_per_thread(tmp_path: Path):
	# given
	file_path = tmp_path / "clip.mp4"
	file_path.write_bytes(b"x")
	fake_pythoncom = MagicMock()
	fake_pythoncom.COINIT_APARTMENTTHREADED = 2
	fake_pythoncom.com_error = FakeComError
	fake_propsys = MagicMock()
	fake_propsys.PSGetPropertyKeyFromName.return_value = "property-key"
	fake_propsys.IID_IPropertyStore = "store-id"
	fake_store = MagicMock()
	fake_variant = MagicMock()
	fake_variant.GetValue.return_value = None
	fake_store.GetValue.return_value = fake_variant
	fake_propsys.SHGetPropertyStoreFromParsingName.return_value = fake_store
	fake_shellcon = MagicMock()
	fake_shellcon.GPS_DEFAULT = 0
	errors: list[BaseException] = []
	ready = threading.Barrier(2)

	def worker():
		try:
			reset_thread_com_state_for_tests()
			with (
				patch("srxy.windows_metadata.windows_tags_supported", return_value=True),
				patch.dict(
					"sys.modules",
					{
						"pythoncom": fake_pythoncom,
						"win32com.propsys": MagicMock(propsys=fake_propsys),
						"win32com.shell": MagicMock(shellcon=fake_shellcon),
					},
				),
			):
				ready.wait(timeout=1)
				_read_windows_keywords(file_path)
		except BaseException as error:
			errors.append(error)

	# when
	threads = [threading.Thread(target=worker) for _ in range(2)]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join()

	# then
	assert errors == []
	assert fake_pythoncom.CoInitializeEx.call_count == 2


def test_given_changed_mode_runtime_when_scanning_files_then_does_not_crash(tmp_path: Path):
	# given
	from srxy.file_search import magic_file_search

	search_root = tmp_path / "docs"
	search_root.mkdir()
	(search_root / "notes.txt").write_text("hello world", encoding="utf-8")
	(search_root / "clip.mp4").write_bytes(b"\x00")

	def fake_has_windows_tags(path: Path) -> bool:
		_ensure_com_initialized()
		return path.suffix.lower() == ".mp4"

	# when
	with (
		patch("srxy.file_search.has_windows_tags", side_effect=fake_has_windows_tags),
		patch("srxy.file_search.iter_windows_metadata_lines", return_value=iter([])),
		patch("srxy.windows_metadata.windows_tags_supported", return_value=True),
	):
		reset_thread_com_state_for_tests()
		fake_pythoncom = MagicMock()
		fake_pythoncom.COINIT_APARTMENTTHREADED = 2
		fake_pythoncom.CoInitializeEx.side_effect = FakeComError(
			_RPC_E_CHANGED_MODE,
			"[WinError 10106] The requested service provider could not be loaded or initialized",
		)
		fake_pythoncom.com_error = FakeComError
		with patch.dict("sys.modules", {"pythoncom": fake_pythoncom}):
			results = magic_file_search(search_root, "hello", search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "notes.txt"
