from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.adapters.inbound.tui.desktop import TextualDesktopAdapter
from srxy.adapters.outbound.os.desktop import OsDesktopAdapter


pytestmark = pytest.mark.unit


def test_given_os_adapter_when_opening_path_then_delegates_to_open_path(tmp_path: Path):
	target = tmp_path / "note.txt"
	target.write_text("hi", encoding="utf-8")
	adapter = OsDesktopAdapter()
	with patch("srxy.adapters.outbound.os.desktop.open_path") as open_path:
		adapter.open_path(target)
	open_path.assert_called_once_with(target)


def test_given_os_adapter_when_copying_text_then_delegates_to_copy_text():
	adapter = OsDesktopAdapter()
	with patch("srxy.adapters.outbound.os.desktop.copy_text") as copy_text:
		adapter.copy_text("hello")
	copy_text.assert_called_once_with("hello")


def test_given_os_adapter_when_revealing_path_then_delegates_to_reveal_path(tmp_path: Path):
	target = tmp_path / "note.txt"
	target.write_text("hi", encoding="utf-8")
	adapter = OsDesktopAdapter()
	with patch("srxy.adapters.outbound.os.desktop.reveal_path") as reveal_path:
		adapter.reveal_path(target)
	reveal_path.assert_called_once_with(target)


def test_given_textual_adapter_when_fallback_needed_then_calls_fallback():
	fallback = MagicMock()
	adapter = TextualDesktopAdapter(copy_fallback=fallback)
	with (
		patch("srxy.adapters.inbound.tui.desktop.platform.system", return_value="Linux"),
		patch("srxy.adapters.inbound.tui.desktop.shutil.which", return_value=None),
	):
		adapter.copy_text("hello")
	fallback.assert_called_once_with("hello")


def test_given_textual_adapter_when_opening_path_then_uses_os_open(tmp_path: Path):
	target = tmp_path / "a.txt"
	target.write_text("x", encoding="utf-8")
	adapter = TextualDesktopAdapter()
	with patch("srxy.adapters.inbound.tui.desktop.open_path") as open_path:
		adapter.open_path(target)
	open_path.assert_called_once_with(target)
