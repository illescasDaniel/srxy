"""Unit tests for persisted settings.json helpers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from srxy.application.settings import (
	load_settings,
	reset_settings,
	set_language_setting,
	settings_file_present,
	settings_path,
)


pytestmark = pytest.mark.unit


def test_given_settings_file_when_reset_then_deletes_and_clears_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	set_language_setting("es")
	assert settings_file_present() is True
	assert load_settings().get("language") == "es"
	assert os.environ.get("SRXY_LANGUAGE") == "es"

	# when
	removed = reset_settings()

	# then
	assert removed is True
	assert settings_file_present() is False
	assert not settings_path().exists()
	assert "SRXY_LANGUAGE" not in os.environ
	assert load_settings() == {}


def test_given_no_settings_file_when_reset_then_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "missing.json"))
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)

	# when
	removed = reset_settings()

	# then
	assert removed is False
	assert settings_file_present() is False
