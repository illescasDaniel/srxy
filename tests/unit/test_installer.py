from __future__ import annotations

import json
from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.manifest import (
	InstallManifest,
	is_srxy_prefix,
	read_manifest,
	write_manifest,
)
from srxy.adapters.inbound.installer.privacy import privacy_disclaimer_html, privacy_disclaimer_text
from srxy.adapters.inbound.installer.uninstall import UNINSTALL_SEARCH_HINT, discover_default_prefix, uninstall_prefix
from srxy.application.install_paths import MANIFEST_NAME


pytestmark = pytest.mark.unit


def test_given_manifest_when_writing_and_reading_then_round_trips(tmp_path: Path):
	# given
	manifest = InstallManifest(
		version="1.5.0",
		prefix=str(tmp_path),
		installed_at="2026-08-02T12:00:00+00:00",
		semantic=True,
		models_prefetched=False,
		vendor_tesseract=True,
		vendor_ffmpeg=True,
	)

	# when
	write_manifest(tmp_path, manifest)
	loaded = read_manifest(tmp_path)

	# then
	assert loaded is not None
	assert loaded.version == "1.5.0"
	assert loaded.semantic is True
	assert loaded.vendor_tesseract is True
	assert (tmp_path / MANIFEST_NAME).is_file()
	payload = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
	assert payload["prefix"] == str(tmp_path)


def test_given_force_gpu_when_creating_controller_then_ai_options_default_on(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_GPU", "1")
	monkeypatch.delenv("SRXY_INSTALLER_FORCE_NO_GPU", raising=False)

	# when
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()

	# then
	assert controller.hasGpu is True
	assert controller.installSemantic is True
	assert controller.prefetchModels is True


def test_given_force_no_gpu_when_creating_controller_then_ai_options_default_off(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	monkeypatch.delenv("SRXY_INSTALLER_FORCE_GPU", raising=False)

	# when
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()

	# then
	assert controller.hasGpu is False
	assert controller.installSemantic is False
	assert controller.prefetchModels is False
	assert "GPU" in str(controller.noGpuMessage)


def test_given_help_keys_when_asking_controller_then_returns_plain_language(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()

	# when / then
	assert "Text in images" in str(controller.helpText("tesseract"))
	assert "Spoken words" in str(controller.helpText("ffmpeg"))
	assert "Similar meaning" in str(controller.helpText("semantic"))
	assert "Hugging Face" in str(controller.helpText("models"))
	assert "No usable GPU" in str(controller.helpText("no_gpu"))


def test_given_privacy_text_when_loading_then_mentions_third_parties():
	# given / when
	text = privacy_disclaimer_text()
	html = privacy_disclaimer_html()

	# then
	assert "Hugging Face" in text
	assert "NVIDIA" in text
	assert "Tesseract" in text
	assert "ffmpeg" in text
	assert "https://huggingface.co/privacy" in text
	assert "https://www.nvidia.com/en-us/about-nvidia/privacy-policy/" in text
	assert "https://github.com/tesseract-ocr/tesseract" in text
	assert "<a href=" in html
	assert "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" in html


def test_given_prefix_with_manifest_when_uninstalling_then_removes_tree(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / "bin").mkdir()
	(prefix / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")
	write_manifest(
		prefix,
		InstallManifest(version="1.5.0", prefix=str(prefix), installed_at="2026-08-02T12:00:00+00:00"),
	)
	apps = tmp_path / ".local" / "share" / "applications"
	apps.mkdir(parents=True)
	desktop = apps / "srxy.desktop"
	desktop.write_text(f"[Desktop Entry]\nExec={prefix}/bin/srxy\n", encoding="utf-8")
	monkeypatch.setenv("HOME", str(tmp_path))

	# when
	uninstall_prefix(prefix)

	# then
	assert not prefix.exists()
	assert not desktop.exists()


def test_given_default_prefix_missing_when_discovering_then_returns_none(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	# given
	monkeypatch.setenv("HOME", str(tmp_path))

	# when / then
	assert discover_default_prefix() is None
	assert MANIFEST_NAME in UNINSTALL_SEARCH_HINT


def test_given_bin_srxy_only_when_checking_prefix_then_accepts(tmp_path: Path):
	# given
	(tmp_path / "bin").mkdir()
	(tmp_path / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	# when / then
	assert is_srxy_prefix(tmp_path) is True
