"""Unit tests for Settings maintenance snapshot / clear helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.application.settings_maintenance import (
	build_settings_snapshot,
	clear_model_kind,
	pending_downloads_for_kind,
)


pytestmark = pytest.mark.unit


def test_given_no_models_when_building_snapshot_then_marks_not_installed(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	monkeypatch.setenv("SRXY_HOME", str(tmp_path / "home"))
	monkeypatch.delenv("SRXY_SEMANTIC_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE_FASTER_WHISPER_MODEL_PATH", raising=False)
	monkeypatch.delenv("SRXY_TRANSCRIBE_TRANSFORMERS_MODEL_PATH", raising=False)
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	snapshot = build_settings_snapshot(busy=False)

	# then
	kinds = [row["kind"] for row in snapshot["models"]]
	assert kinds == ["semantic_text", "semantic_image", "transcribe", "all"]
	assert all(row["installed"] is False for row in snapshot["models"])
	assert snapshot["cache"]["present"] is False
	assert "preferences" in snapshot
	assert snapshot["busy"] is False


def test_given_installed_text_model_when_building_snapshot_then_reports_size(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	model_dir = tmp_path / "semantic-model"
	model_dir.mkdir()
	(model_dir / "config.json").write_text("{}", encoding="utf-8")
	(model_dir / "weights.bin").write_bytes(b"z" * 2048)
	monkeypatch.setenv("SRXY_SEMANTIC_MODEL_PATH", str(model_dir))
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))

	# when
	snapshot = build_settings_snapshot(busy=True)

	# then
	text_row = next(row for row in snapshot["models"] if row["kind"] == "semantic_text")
	all_row = next(row for row in snapshot["models"] if row["kind"] == "all")
	assert text_row["installed"] is True
	assert "2 KiB" in text_row["statusText"] or "KiB" in text_row["statusText"]
	assert all_row["installed"] is True
	assert snapshot["busy"] is True


def test_given_kind_when_clearing_then_dispatches_to_model_store():
	# given / when / then
	with patch("srxy.application.settings_maintenance.clear_semantic_text_model") as clear_text:
		clear_model_kind("semantic_text")
		clear_text.assert_called_once_with()
	with patch("srxy.application.settings_maintenance.clear_all_models") as clear_all:
		clear_model_kind("all")
		clear_all.assert_called_once_with()


def test_given_all_kind_when_pending_downloads_then_queues_three_kinds():
	# given / when
	items = pending_downloads_for_kind("all")

	# then
	assert [item.kind for item in items] == ["semantic_text", "semantic_image", "transcribe"]
