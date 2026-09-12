from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.adapters.outbound.metadata.windows_metadata import (
	_ensure_com_initialized,
	_read_searchable_property_entries,
	_read_windows_keywords,
	has_windows_tags,
	iter_windows_metadata_lines,
	normalize_windows_keywords,
	reset_isolated_worker_for_tests,
	reset_thread_com_state_for_tests,
	windows_tags_supported,
)
from srxy.adapters.outbound.metadata.windows_metadata_worker import _handle_request


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
	with patch(
		"srxy.adapters.outbound.metadata.windows_metadata._read_searchable_property_entries",
		return_value=[("Windows tag", "cursor"), ("Windows tag", "quarterly")],
	):
		lines = list(iter_windows_metadata_lines(file_path))

	# then
	assert lines == [(1, "[Windows tag] cursor"), (2, "[Windows tag] quarterly")]


def test_given_property_entries_when_iterating_windows_lines_then_yields_labeled_values(tmp_path: Path):
	# given
	file_path = tmp_path / "report.docx"

	# when
	with patch(
		"srxy.adapters.outbound.metadata.windows_metadata._read_searchable_property_entries",
		return_value=[
			("Program name", "Microsoft Office Word"),
			("Last saved by", "Daniel Illescas"),
		],
	):
		lines = list(iter_windows_metadata_lines(file_path))

	# then
	assert lines == [
		(1, "[Program name] Microsoft Office Word"),
		(2, "[Last saved by] Daniel Illescas"),
	]


def test_given_property_store_error_when_reading_keywords_then_returns_empty(tmp_path: Path):
	# given
	file_path = tmp_path / "clip.mp4"

	# when
	with (
		patch("srxy.adapters.outbound.metadata.windows_metadata.windows_tags_supported", return_value=True),
		patch(
			"srxy.adapters.outbound.metadata.windows_metadata._open_property_store",
			side_effect=OSError("access denied"),
		),
	):
		tags = list(iter_windows_metadata_lines(file_path))

	# then
	assert tags == []


def test_given_non_windows_platform_when_checking_support_then_returns_false():
	# when
	with patch("srxy.adapters.outbound.metadata.windows_metadata.sys.platform", "linux"):
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
		patch("srxy.adapters.outbound.metadata.windows_metadata.windows_tags_supported", return_value=True),
		patch(
			"srxy.adapters.outbound.metadata.windows_metadata._read_property_value",
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
		patch("srxy.adapters.outbound.metadata.windows_metadata.windows_tags_supported", return_value=True),
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
			ready.wait(timeout=1)
			_read_windows_keywords(file_path)
		except BaseException as error:
			errors.append(error)

	# when
	with (
		patch("srxy.adapters.outbound.metadata.windows_metadata.windows_tags_supported", return_value=True),
		patch.dict(
			"sys.modules",
			{
				"pythoncom": fake_pythoncom,
				"win32com": MagicMock(),
				"win32com.propsys": MagicMock(propsys=fake_propsys),
				"win32com.shell": MagicMock(shellcon=fake_shellcon),
			},
		),
	):
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
	from srxy.application.use_cases.search_files import magic_file_search

	search_root = tmp_path / "docs"
	search_root.mkdir()
	(search_root / "notes.txt").write_text("hello world", encoding="utf-8")
	(search_root / "clip.mp4").write_bytes(b"\x00")

	def fake_has_windows_metadata(path: Path) -> bool:
		_ensure_com_initialized()
		return path.suffix.lower() == ".mp4"

	# when
	with (
		patch(
			"srxy.adapters.outbound.content.line_sources.has_windows_searchable_metadata",
			side_effect=fake_has_windows_metadata,
		),
		patch("srxy.adapters.outbound.content.line_sources.iter_windows_metadata_lines", return_value=iter([])),
		patch("srxy.adapters.outbound.metadata.windows_metadata.windows_tags_supported", return_value=True),
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


def test_given_windows_platform_when_reading_searchable_entries_then_uses_isolated_worker(tmp_path: Path):
	# given -- real Windows dispatches through the crash-isolated subprocess path,
	# not the in-process ``_open_property_store`` call that a native SEH fault
	# (0xc0000002) can take down.
	file_path = tmp_path / "broken.jpg"

	# when
	with (
		patch("srxy.adapters.outbound.metadata.windows_metadata.sys.platform", "win32"),
		patch(
			"srxy.adapters.outbound.metadata.windows_metadata._read_searchable_property_entries_isolated",
			return_value=[("Windows tag", "cursor")],
		) as isolated,
		patch("srxy.adapters.outbound.metadata.windows_metadata._read_searchable_property_entries_direct") as direct,
		patch("srxy.adapters.outbound.metadata.windows_metadata.windows_metadata_supported", return_value=True),
	):
		entries = _read_searchable_property_entries(file_path)

	# then
	assert entries == [("Windows tag", "cursor")]
	isolated.assert_called_once_with(file_path)
	direct.assert_not_called()


def test_given_dead_worker_process_when_reading_isolated_entries_then_fails_soft_and_respawns(tmp_path: Path):
	# given -- simulates a native SEH fault killing the worker subprocess: the
	# pipe hits EOF (``readline()`` returns ``""``) instead of raising anything
	# Python can catch.
	from srxy.adapters.outbound.metadata import windows_metadata as module

	reset_isolated_worker_for_tests()
	crashed_worker = MagicMock()
	crashed_worker.poll.return_value = None
	crashed_worker.stdin = MagicMock()
	crashed_worker.stdout = MagicMock()
	crashed_worker.stdout.readline.return_value = ""

	try:
		with patch.object(module, "_spawn_isolated_worker", return_value=crashed_worker):
			entries = module._read_searchable_property_entries_isolated(tmp_path / "broken.jpg")

		# then
		assert entries == []
		# The dead worker must be dropped so the next call respawns a clean one.
		assert module._isolated_worker_process is None
	finally:
		reset_isolated_worker_for_tests()


def test_given_healthy_worker_process_when_reading_isolated_entries_then_reuses_it(tmp_path: Path):
	# given
	from srxy.adapters.outbound.metadata import windows_metadata as module

	reset_isolated_worker_for_tests()
	healthy_worker = MagicMock()
	healthy_worker.poll.return_value = None
	healthy_worker.stdin = MagicMock()
	healthy_worker.stdout = MagicMock()
	healthy_worker.stdout.readline.return_value = json.dumps({"entries": [["Windows tag", "cursor"]]}) + "\n"

	try:
		with patch.object(module, "_spawn_isolated_worker", return_value=healthy_worker) as spawn:
			first = module._read_searchable_property_entries_isolated(tmp_path / "clip.mp4")
			second = module._read_searchable_property_entries_isolated(tmp_path / "clip2.mp4")

		# then -- one worker process serves both requests.
		assert first == [("Windows tag", "cursor")]
		assert second == [("Windows tag", "cursor")]
		spawn.assert_called_once()
		assert healthy_worker.stdin.write.call_count == 2
	finally:
		reset_isolated_worker_for_tests()


def test_given_hung_worker_when_reading_isolated_entries_then_times_out_and_fails_soft(tmp_path: Path):
	# given -- a worker that never responds (hangs inside the property handler)
	# must not block the caller forever.
	import time

	from srxy.adapters.outbound.metadata import windows_metadata as module

	reset_isolated_worker_for_tests()
	hung_worker = MagicMock()
	hung_worker.poll.return_value = None
	hung_worker.stdin = MagicMock()
	hung_worker.stdout = MagicMock()
	hung_worker.stdout.readline.side_effect = lambda: time.sleep(10) or ""

	try:
		with (
			patch.object(module, "_spawn_isolated_worker", return_value=hung_worker),
			patch.object(module, "_ISOLATED_WORKER_TIMEOUT_SECONDS", 0.05),
		):
			entries = module._read_searchable_property_entries_isolated(tmp_path / "broken.jpg")

		# then
		assert entries == []
		assert module._isolated_worker_process is None
	finally:
		reset_isolated_worker_for_tests()


def test_given_valid_request_when_worker_handles_it_then_returns_direct_entries(tmp_path: Path):
	# given
	file_path = tmp_path / "report.docx"

	# when
	with patch(
		"srxy.adapters.outbound.metadata.windows_metadata._read_searchable_property_entries_direct",
		return_value=[("Program name", "Microsoft Office Word")],
	):
		response = _handle_request(json.dumps({"path": str(file_path)}))

	# then
	assert json.loads(response) == {"entries": [["Program name", "Microsoft Office Word"]]}


def test_given_malformed_request_when_worker_handles_it_then_returns_empty_entries():
	# then
	assert json.loads(_handle_request("not-json")) == {"entries": []}
	assert json.loads(_handle_request(json.dumps({}))) == {"entries": []}
