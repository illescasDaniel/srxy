from __future__ import annotations

import io
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.model_store import (
	SEMANTIC_IMAGE_MODEL_ID,
	SEMANTIC_TEXT_MODEL_ID,
	download_semantic_text_model,
	ensure_semantic_image_model,
	ensure_semantic_text_model,
	ensure_transcribe_model,
	is_model_installed,
	main,
	semantic_text_model_dir,
	transcribe_faster_whisper_model_dir,
	transcribe_faster_whisper_repo_id,
)


pytestmark = pytest.mark.unit


def test_given_model_markers_when_checking_installation_then_detects_cached_model(tmp_path: Path):
	# given
	model_dir = tmp_path / "semantic-model"
	model_dir.mkdir()
	(model_dir / "modules.json").write_text("{}", encoding="utf-8")

	# when / then
	assert is_model_installed(model_dir) is True


def test_given_empty_directory_when_checking_installation_then_returns_false(tmp_path: Path):
	# given
	model_dir = tmp_path / "empty"
	model_dir.mkdir()

	# when / then
	assert is_model_installed(model_dir) is False


def test_given_cached_model_when_ensuring_text_model_then_skips_download(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	model_dir = tmp_path / "semantic-model"
	model_dir.mkdir()
	(model_dir / "config.json").write_text("{}", encoding="utf-8")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))

	with patch("srxy.model_store.download_model") as download:
		# when
		ready = ensure_semantic_text_model(interactive=False)

	# then
	assert ready is True
	download.assert_not_called()
	assert semantic_text_model_dir() == model_dir


def test_given_missing_model_when_user_declines_then_ensure_returns_false(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))
	stdin = io.StringIO("n\n")
	stdout = io.StringIO()

	with patch("srxy.model_store.download_model") as download:
		# when
		ready = ensure_semantic_text_model(interactive=True, stdin=stdin, stdout=stdout)

	# then
	assert ready is False
	download.assert_not_called()


def test_given_missing_model_when_user_accepts_then_downloads_to_cache(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))

	def fake_download(model_id: str, target_dir: Path):
		target_dir.mkdir(parents=True, exist_ok=True)
		(target_dir / "modules.json").write_text("{}", encoding="utf-8")
		assert model_id == SEMANTIC_TEXT_MODEL_ID

	with patch("srxy.model_store.download_model", side_effect=fake_download) as download:
		# when
		ready = ensure_semantic_text_model(interactive=False, auto_download=True)

	# then
	assert ready is True
	download.assert_called_once()
	assert is_model_installed(semantic_text_model_dir())


def test_given_auto_download_when_ensuring_image_model_then_downloads_without_prompt(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))

	def fake_download(model_id: str, target_dir: Path):
		target_dir.mkdir(parents=True, exist_ok=True)
		(target_dir / "modules.json").write_text("{}", encoding="utf-8")
		assert model_id == SEMANTIC_IMAGE_MODEL_ID

	with patch("srxy.model_store.download_model", side_effect=fake_download) as download:
		# when
		ready = ensure_semantic_image_model(interactive=False, auto_download=True)

	# then
	assert ready is True
	download.assert_called_once()


def test_given_download_cli_when_target_is_semantic_text_then_downloads_model(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))

	with patch("srxy.model_store.download_semantic_text_model") as download_text:
		# when
		exit_code = main(["semantic-text"])

	# then
	assert exit_code == 0
	download_text.assert_called_once()


def test_given_download_helper_when_called_then_sets_model_path_env(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))

	def fake_download(model_id: str, target_dir: Path):
		target_dir.mkdir(parents=True, exist_ok=True)
		(target_dir / "modules.json").write_text("{}", encoding="utf-8")

	with patch("srxy.model_store.download_model", side_effect=fake_download):
		# when
		download_semantic_text_model()

	# then
	assert os.environ["SRXY_SEMANTIC_MODEL_PATH"] == str(semantic_text_model_dir())


def test_given_auto_download_when_ensuring_transcribe_model_then_downloads_without_prompt(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))

	def fake_download(model_id: str, target_dir: Path):
		target_dir.mkdir(parents=True, exist_ok=True)
		(target_dir / "model.bin").write_bytes(b"model")
		assert model_id == transcribe_faster_whisper_repo_id()

	with (
		patch("srxy.model_store.download_model", side_effect=fake_download) as download,
		patch("srxy.device.resolve_transcribe_device", return_value="cpu"),
	):
		# when
		ready = ensure_transcribe_model(interactive=False, auto_download=True)

	# then
	assert ready is True
	download.assert_called_once()
	assert is_model_installed(transcribe_faster_whisper_model_dir())
