"""Installer cancel protocol and uninstall user-data cleanup."""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.cancel import InstallCancelledError, cancel_requested, raise_if_cancelled
from srxy.adapters.inbound.installer.uninstall import cleanup_user_data


pytestmark = pytest.mark.unit


def test_given_cancel_file_when_requested_then_cancel_requested_true(tmp_path: Path):
	marker = tmp_path / "cancel.request"
	marker.write_text("1", encoding="utf-8")
	assert cancel_requested(str(marker))


def test_given_cancel_file_when_raise_if_cancelled_then_raises(tmp_path: Path):
	marker = tmp_path / "cancel.request"
	marker.write_text("1", encoding="utf-8")
	with pytest.raises(InstallCancelledError):
		raise_if_cancelled(str(marker), "stopped")


def test_given_user_data_dirs_when_cleanup_then_removes_cache_and_settings(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):

	cache_root = tmp_path / "cache"
	cache_root.mkdir()
	db = cache_root / "cache.db"
	db.write_bytes(b"data")
	key = cache_root / ".cache_key"
	key.write_bytes(b"key")
	settings = tmp_path / "config" / "srxy" / "settings.json"
	settings.parent.mkdir(parents=True)
	settings.write_text('{"language": "en"}\n', encoding="utf-8")

	monkeypatch.setenv("SRXY_CACHE_DIR", str(cache_root))
	monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
	monkeypatch.delenv("SRXY_HOME", raising=False)
	monkeypatch.delenv("SRXY_SETTINGS_PATH", raising=False)

	cleanup_user_data(remove_cache=True, remove_settings=True, remove_models=False)

	assert not db.exists()
	assert not key.exists()
	from srxy.application.settings import settings_path

	assert not settings_path().exists()
