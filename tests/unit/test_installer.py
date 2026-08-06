from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest
from tests.helpers import set_fake_home

from srxy.adapters.inbound.installer.install import write_launcher
from srxy.adapters.inbound.installer.manifest import (
	InstallManifest,
	is_non_empty_foreign_prefix,
	is_srxy_prefix,
	looks_like_partial_srxy_prefix,
	prefix_needs_confirmation,
	read_manifest,
	require_matching_manifest,
	write_manifest,
)
from srxy.adapters.inbound.installer.privacy import privacy_disclaimer_html, privacy_disclaimer_text
from srxy.adapters.inbound.installer.uninstall import discover_default_prefix, uninstall_prefix, uninstall_search_hint
from srxy.application.install_paths import MANIFEST_NAME


pytestmark = [pytest.mark.unit, pytest.mark.xdist_group("gui")]


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
		path_rc=str(tmp_path / ".zshrc"),
		installer_version="1",
		user_icons=[str(tmp_path / "icon.png")],
	)

	# when
	write_manifest(tmp_path, manifest)
	loaded = read_manifest(tmp_path)

	# then
	assert loaded is not None
	assert loaded.version == "1.5.0"
	assert loaded.semantic is True
	assert loaded.vendor_tesseract is True
	assert loaded.path_rc.endswith(".zshrc")
	assert loaded.installer_version == "1"
	assert loaded.user_icons == [str(tmp_path / "icon.png")]
	assert (tmp_path / MANIFEST_NAME).is_file()
	payload = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
	assert payload["prefix"] == str(tmp_path)


def test_given_force_gpu_when_creating_controller_then_semantic_on_prefetch_off(
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
	assert controller.prefetchModels is False


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


def test_given_system_locale_tags_when_creating_controller_then_preselects_mapped_packs(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)
	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.tessdata_langs.system_preferred_locale_tags",
		lambda: ("fr", "de"),
	)

	class _FakeLocale:
		@staticmethod
		def system():
			return _FakeLocale()

		def uiLanguages(self):
			return ["es-ES", "en-US"]

	monkeypatch.setattr("PySide6.QtCore.QLocale", _FakeLocale)

	# when
	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer.controller import InstallerController

	if QCoreApplication.instance() is None:
		QCoreApplication([])
	controller = InstallerController()

	# then — eng/osd always; fr→fra, de→deu, es→spa from system/Qt tags
	assert controller.tessdataLangsCsv.split(",")[:2] == ["eng", "osd"]
	selected = set(controller.tessdataLangsCsv.split(","))
	assert {"fra", "deu", "spa"}.issubset(selected)
	assert "English" in str(controller.tessdataLangsSummary)
	assert "Orientation detection" in str(controller.tessdataLangsSummary)


def test_given_help_keys_when_asking_controller_then_returns_plain_language(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()
	controller.setLanguage("en")

	# when / then
	assert "Text in images" in str(controller.helpText("tesseract"))
	assert "Audio/video helper" in str(controller.helpText("ffmpeg"))
	assert "Smarter search" in str(controller.helpText("semantic"))
	assert "Hugging Face" in str(controller.helpText("models"))
	assert "No usable GPU" in str(controller.helpText("no_gpu"))


def test_given_spanish_when_set_on_installer_then_ui_strings_switch(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()
	controller.setLanguage("en")
	assert "What do you want" in controller.i18nTr("installer.mode.title")

	# when
	controller.setLanguage("es")

	# then
	assert controller.language == "es"
	assert "quieres hacer" in controller.i18nTr("installer.mode.title").lower()
	assert "idioma" in controller.i18nTr("installer.language").lower()
	assert "gpu" in controller.noGpuMessage.lower()
	assert "Texto en imágenes" in str(controller.helpText("tesseract"))
	assert "aviso de privacidad" in controller.privacyText.lower()
	controller.setLanguage("en")
	assert "third-party notice" in controller.privacyText.lower()
	assert "marker file" in controller.uninstallHint.lower()


def test_given_language_when_writing_privacy_utf8_then_uses_bom_and_locale(
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer.privacy import write_privacy_notice_utf8

	en = tmp_path / "privacy-en.txt"
	es = tmp_path / "privacy-es.txt"

	# when
	write_privacy_notice_utf8(en, language="en")
	write_privacy_notice_utf8(es, language="es")

	# then
	assert en.read_bytes()[:3] == b"\xef\xbb\xbf"
	assert es.read_bytes()[:3] == b"\xef\xbb\xbf"
	en_text = en.read_text(encoding="utf-8-sig")
	es_text = es.read_text(encoding="utf-8-sig")
	assert "privacy" in en_text.lower()
	assert "aviso" in es_text.lower()
	assert "Ã" not in en_text
	assert "Ã" not in es_text


def test_given_privacy_when_loading_then_mentions_both_cache_paths():
	# given
	from srxy.i18n import set_language

	set_language("en")

	# when
	text = privacy_disclaimer_text()

	# then
	assert "%LOCALAPPDATA%\\srxy" in text
	assert "~/.cache/srxy" in text
	assert "Disclaimer of Warranties" in text
	assert "without any warranty" in text.lower()


def test_given_privacy_text_when_loading_then_mentions_third_parties():
	# given
	from srxy.i18n import set_language

	set_language("en")

	# when
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
	assert "Disclaimer of Warranties" in html
	assert "without any warranty" in html.lower()


def test_given_spanish_when_loading_privacy_then_translates_prose():
	# given
	from srxy.i18n import set_language

	set_language("es")

	# when
	text = privacy_disclaimer_text()
	html = privacy_disclaimer_html()

	# then
	assert "aviso de privacidad" in text.lower()
	assert "terceros" in text.lower()
	assert "Sitio:" in text or "Sitio:" in html
	assert "Privacidad:" in text or "Privacidad:" in html
	assert "https://huggingface.co/privacy" in html
	assert "srxy — aviso" in html.lower()
	assert "qué puede descargar srxy" in html.lower()
	assert "exención de garantías" in html.lower()
	assert "sin ninguna garantía" in html.lower()
	assert "este appimage" not in html.lower()
	set_language("en")
	en_html = privacy_disclaimer_html()
	assert "this appimage" not in en_html.lower()
	assert "what srxy may download" in en_html.lower()
	assert "acknowledgment box" not in en_html.lower()
	assert "disclaimer of warranties" in en_html.lower()


def test_given_darwin_when_loading_installer_privacy_then_lists_macos_vendor_sources(
	monkeypatch: pytest.MonkeyPatch,
):
	from srxy.adapters.inbound.installer import privacy as privacy_mod
	from srxy.i18n import set_language

	set_language("en")
	monkeypatch.setattr(privacy_mod.platform, "system", lambda: "Darwin")

	text = privacy_disclaimer_text()
	assert "formulae.brew.sh/formula/tesseract" in text
	assert "ffmpeg.martin-riedl.de" in text
	assert "BtbN/FFmpeg-Builds" not in text
	assert "DanielMYT/tesseract-static" not in text
	assert "appimage" not in text.lower()


def test_given_linux_when_loading_installer_privacy_then_lists_linux_vendor_sources(
	monkeypatch: pytest.MonkeyPatch,
):
	from srxy.adapters.inbound.installer import privacy as privacy_mod
	from srxy.i18n import set_language

	set_language("en")
	monkeypatch.setattr(privacy_mod.platform, "system", lambda: "Linux")

	text = privacy_disclaimer_text()
	assert "DanielMYT/tesseract-static" in text
	assert "BtbN/FFmpeg-Builds" in text
	assert "formulae.brew.sh/formula/tesseract" not in text
	assert "ffmpeg.martin-riedl.de" not in text


def test_given_prefix_with_manifest_when_uninstalling_then_removes_tree(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / "bin").mkdir()
	(prefix / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")
	icon_path = tmp_path / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "srxy.png"
	icon_path.parent.mkdir(parents=True)
	icon_path.write_bytes(b"png")
	write_manifest(
		prefix,
		InstallManifest(
			version="1.5.0",
			prefix=str(prefix),
			installed_at="2026-08-02T12:00:00+00:00",
			user_icons=[str(icon_path)],
		),
	)
	apps = tmp_path / ".local" / "share" / "applications"
	apps.mkdir(parents=True)
	desktop = apps / "srxy.desktop"
	desktop.write_text(f"[Desktop Entry]\nExec={prefix}/bin/srxy\n", encoding="utf-8")
	set_fake_home(monkeypatch, tmp_path)

	# when
	uninstall_prefix(prefix)

	# then
	assert not prefix.exists()
	assert not desktop.exists()
	assert not icon_path.exists()


def test_given_default_prefix_missing_when_discovering_then_returns_none(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	# given
	set_fake_home(monkeypatch, tmp_path)

	# when / then
	assert discover_default_prefix() is None
	assert MANIFEST_NAME in uninstall_search_hint()


def test_given_partial_default_prefix_when_discovering_then_returns_path(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	# given
	from srxy.application.install_paths import default_install_prefix

	set_fake_home(monkeypatch, tmp_path)
	prefix = default_install_prefix()
	prefix.mkdir(parents=True)
	(prefix / "vendor" / "uv").mkdir(parents=True)
	(prefix / "vendor" / "uv" / "uv").write_text("x", encoding="utf-8")

	# when / then
	assert discover_default_prefix() == prefix.resolve()


def test_given_bin_srxy_only_when_checking_prefix_then_rejects(tmp_path: Path):
	# given
	(tmp_path / "bin").mkdir()
	(tmp_path / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	# when / then
	assert is_srxy_prefix(tmp_path) is False
	assert looks_like_partial_srxy_prefix(tmp_path) is True


def test_given_bin_srxy_only_when_uninstalling_then_removes_orphan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	home = tmp_path / "home"
	home.mkdir()
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / "bin").mkdir()
	(prefix / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")
	set_fake_home(monkeypatch, home)

	# when
	uninstall_prefix(prefix)

	# then
	assert not prefix.exists()


def test_given_prefix_mismatch_when_uninstalling_then_removes_orphan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	write_manifest(
		prefix,
		InstallManifest(version="1.5.0", prefix=str(tmp_path / "other"), installed_at="2026-08-02T12:00:00+00:00"),
	)
	set_fake_home(monkeypatch, tmp_path)

	# when
	uninstall_prefix(prefix)

	# then
	assert not prefix.exists()


def test_given_partial_venv_when_checking_then_flags_partial(tmp_path: Path):
	# given
	(tmp_path / ".venv").mkdir()

	# when / then
	assert looks_like_partial_srxy_prefix(tmp_path) is True
	assert is_non_empty_foreign_prefix(tmp_path) is True
	assert is_srxy_prefix(tmp_path) is False


def test_given_macos_failed_online_leftovers_when_uninstalling_then_removes_prefix(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given: failed online install wrote logs but never a manifest/uv binary
	from srxy.application.install_paths import default_install_prefix

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	prefix = default_install_prefix()
	(prefix / "logs").mkdir(parents=True)
	(prefix / "vendor").mkdir(parents=True)
	(prefix / "logs" / "installer-online.log").write_text("install failed\n", encoding="utf-8")

	# when / then
	assert looks_like_partial_srxy_prefix(prefix) is True
	assert discover_default_prefix() == prefix.resolve()
	uninstall_prefix(prefix)
	assert not prefix.exists()


def test_given_macos_srxy_app_only_when_checking_then_flags_partial(tmp_path: Path):
	# given
	(tmp_path / "Srxy.app" / "Contents" / "MacOS").mkdir(parents=True)
	(tmp_path / "Srxy.app" / "Contents" / "MacOS" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	# when / then
	assert looks_like_partial_srxy_prefix(tmp_path) is True
	assert is_srxy_prefix(tmp_path) is False


def test_given_foreign_notes_only_when_checking_then_not_partial(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

	# when / then
	assert looks_like_partial_srxy_prefix(tmp_path) is False
	assert is_non_empty_foreign_prefix(tmp_path) is True


def test_given_home_directory_when_checking_confirmation_then_requires_confirm(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	set_fake_home(monkeypatch, tmp_path)

	# when / then
	assert prefix_needs_confirmation(tmp_path) is True


def test_given_hidden_home_child_when_checking_confirmation_then_requires_confirm(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	set_fake_home(monkeypatch, tmp_path)
	dot_dir = tmp_path / ".hidden"

	# when / then
	assert prefix_needs_confirmation(dot_dir) is True


def test_given_outside_home_when_checking_confirmation_then_requires_confirm(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	set_fake_home(monkeypatch, tmp_path / "home")
	outside = tmp_path / "opt" / "srxy"

	# when / then
	assert prefix_needs_confirmation(outside) is True


def test_given_unsafe_prefix_when_uninstalling_without_confirm_then_raises(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	set_fake_home(monkeypatch, tmp_path)
	write_manifest(
		tmp_path,
		InstallManifest(version="1.5.0", prefix=str(tmp_path), installed_at="2026-08-02T12:00:00+00:00"),
	)

	# when / then
	with pytest.raises(RuntimeError, match="not allowed"):
		uninstall_prefix(tmp_path)


def test_given_unsafe_prefix_when_starting_install_then_opens_confirm_without_progress(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	set_fake_home(monkeypatch, tmp_path)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()
	controller.setPrivacyAck(True)
	controller.setPrefix(str(tmp_path))

	# when
	controller.startInstall()

	# then
	assert bool(controller.unsafeConfirmOpen) is True
	assert str(controller.page) != "progress"
	assert bool(controller.busy) is False
	assert str(tmp_path) in str(controller.unsafeConfirmMessage)


def test_given_unsafe_confirm_accepted_when_installing_then_passes_confirm_unsafe(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	import os
	import threading
	import time
	from collections.abc import Callable

	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer import controller as controller_mod
	from srxy.adapters.inbound.installer.controller import InstallerController
	from srxy.adapters.inbound.installer.install import InstallOptions
	from srxy.adapters.inbound.installer.manifest import InstallManifest

	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	if QCoreApplication.instance() is None:
		QCoreApplication([])

	set_fake_home(monkeypatch, tmp_path)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	captured: dict[str, object] = {}
	done = threading.Event()

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int, int, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
		task_offset: int = 0,
		task_total: int | None = None,
	) -> InstallManifest:
		del progress, task_offset, task_total
		captured["confirm_unsafe"] = options.confirm_unsafe
		captured["prefix"] = options.prefix
		if status is not None:
			status("ok")
		if task is not None:
			task(1, 1, "ok")
		done.set()
		return InstallManifest(
			version="0.0.0",
			prefix=str(options.prefix),
			installed_at="2026-08-02T12:00:00+00:00",
		)

	monkeypatch.setattr(controller_mod, "install_srxy", fake_install)
	controller = InstallerController()
	controller.setPrivacyAck(True)
	controller.setPrefix(str(tmp_path / ".hidden"))
	controller.startInstall()
	assert bool(controller.unsafeConfirmOpen) is True

	# when
	controller.acceptUnsafeConfirm()
	assert done.wait(5.0)
	deadline = time.monotonic() + 5.0
	while bool(controller.busy) and time.monotonic() < deadline:
		QCoreApplication.processEvents()
		time.sleep(0.01)
	controller.shutdown()

	# then
	assert captured.get("confirm_unsafe") is True
	assert bool(controller.unsafeConfirmOpen) is False
	assert bool(controller.busy) is False


def test_given_unsafe_confirm_rejected_when_installing_then_stays_and_shows_error(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	set_fake_home(monkeypatch, tmp_path)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()
	controller.setPrivacyAck(True)
	controller.setPrefix(str(tmp_path))
	controller.startInstall()

	# when
	controller.rejectUnsafeConfirm()

	# then
	assert bool(controller.unsafeConfirmOpen) is False
	assert bool(controller.busy) is False
	assert str(controller.page) != "progress"
	assert len(str(controller.error)) > 0


def test_given_foreign_non_empty_prefix_when_starting_install_then_inline_error(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	foreign = home / "Applications" / "other"
	foreign.mkdir(parents=True)
	(foreign / "notes.txt").write_text("x", encoding="utf-8")
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()
	controller.setPrivacyAck(True)
	controller.setPrefix(str(foreign))

	# when
	controller.startInstall()

	# then
	assert bool(controller.unsafeConfirmOpen) is False
	assert str(controller.page) != "progress"
	assert bool(controller.busy) is False
	assert len(str(controller.error)) > 0


def test_given_uninstall_when_started_then_shows_removing_status_and_indeterminate_bar(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given — uninstall uses a spinner, not file progress
	import threading
	import time
	from collections.abc import Callable
	from typing import cast

	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer import controller as controller_mod
	from srxy.adapters.inbound.installer.controller import InstallerController
	from srxy.adapters.inbound.installer.manifest import InstallManifest, write_manifest

	if QCoreApplication.instance() is None:
		QCoreApplication([])

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	write_manifest(
		prefix,
		InstallManifest(version="1.5.0", prefix=str(prefix), installed_at="2026-08-02T12:00:00+00:00"),
	)
	started = threading.Event()
	release = threading.Event()

	def fake_uninstall(
		path: Path,
		*,
		status: Callable[[str], None] | None = None,
		confirm_unsafe: bool = False,
	):
		del path, confirm_unsafe
		if status is not None:
			status("Removing srxy app…")
		started.set()
		assert release.wait(5.0)

	monkeypatch.setattr(controller_mod, "uninstall_prefix", fake_uninstall)
	controller = InstallerController()
	controller.setUninstallPrefix(str(prefix))

	# when
	controller.startUninstall()
	assert started.wait(5.0)
	deadline = time.monotonic() + 2.0
	while time.monotonic() < deadline:
		QCoreApplication.processEvents()
		if "Removing srxy app" in str(controller.status):
			break
		time.sleep(0.01)

	# then — busy with indeterminate bar while deleting
	assert bool(controller.busy) is True
	assert bool(controller.progressDeterminate) is False
	assert "Removing srxy app" in str(controller.status)

	release.set()
	deadline = time.monotonic() + 5.0
	while bool(controller.busy) and time.monotonic() < deadline:
		QCoreApplication.processEvents()
		time.sleep(0.01)
	controller.shutdown()

	assert bool(controller.finished) is True
	assert cast(float, controller.progressValue) == 1.0
	assert bool(controller.busy) is False


def test_given_uninstall_failed_missing_install_when_going_back_then_returns_to_uninstall_page(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given — uninstall of a folder without an srxy manifest fails on the progress page
	import time

	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer.controller import InstallerController

	if QCoreApplication.instance() is None:
		QCoreApplication([])

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	controller = InstallerController()
	controller.setMode("uninstall")
	controller.setUninstallPrefix(str(prefix))
	controller.goNext()
	assert str(controller.page) == "uninstall"
	controller.startUninstall()
	deadline = time.monotonic() + 5.0
	while bool(controller.busy) and time.monotonic() < deadline:
		QCoreApplication.processEvents()
		time.sleep(0.01)
	controller.shutdown()
	assert str(controller.page) == "progress"
	assert bool(controller.busy) is False
	assert MANIFEST_NAME in str(controller.error)

	# when
	controller.goBack()

	# then — back must leave the failed progress page so the user can pick another path
	assert str(controller.page) == "uninstall"
	assert str(controller.error) == ""
	assert bool(controller.finished) is False


def test_given_reinstall_mode_when_going_next_then_follows_install_page_order(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()
	controller.setMode("reinstall")
	assert str(controller.mode) == "reinstall"

	# when / then — same wizard pages as install
	controller.goNext()
	assert str(controller.page) == "prefix"
	controller.goNext()
	assert str(controller.page) == "privacy"
	controller.setPrivacyAck(True)
	controller.goNext()
	assert str(controller.page) == "options"
	controller.goNext()
	assert str(controller.page) == "tessdata"
	controller.goNext()
	assert str(controller.page) == "path"


def test_given_tesseract_off_when_going_next_then_skips_tessdata_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.controller.vendor_downloads_supported",
		lambda: True,
	)
	from srxy.adapters.inbound.installer.controller import InstallerController

	controller = InstallerController()
	controller.setPrivacyAck(True)
	controller.setDownloadTesseract(False)
	# Advance to options
	controller.goNext()  # prefix
	controller.goNext()  # privacy
	controller.goNext()  # options
	assert str(controller.page) == "options"

	# when
	controller.goNext()

	# then
	assert str(controller.page) == "path"
	controller.goBack()
	assert str(controller.page) == "options"


def test_given_non_srxy_prefix_when_starting_reinstall_then_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	from srxy.adapters.inbound.installer.controller import InstallerController

	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	controller = InstallerController()
	controller.setMode("reinstall")
	controller.setPrivacyAck(True)
	controller.setPrefix(str(prefix))

	# when
	controller.startReinstall()

	# then
	assert str(controller.page) != "progress"
	assert bool(controller.busy) is False
	assert "not an srxy install" in str(controller.error).lower()


def test_given_srxy_prefix_when_starting_reinstall_then_uninstalls_then_installs(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	import threading
	import time
	from collections.abc import Callable
	from typing import cast

	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer import controller as controller_mod
	from srxy.adapters.inbound.installer.controller import InstallerController
	from srxy.adapters.inbound.installer.install import InstallOptions

	if QCoreApplication.instance() is None:
		QCoreApplication([])

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	write_manifest(
		prefix,
		InstallManifest(version="1.5.0", prefix=str(prefix), installed_at="2026-08-02T12:00:00+00:00"),
	)
	calls: list[str] = []
	release = threading.Event()

	def fake_uninstall(
		path: Path,
		*,
		status: Callable[[str], None] | None = None,
		confirm_unsafe: bool = False,
	):
		del confirm_unsafe
		calls.append(f"uninstall:{path}")
		if status is not None:
			status("Removing srxy app…")
		assert release.wait(5.0)

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int, int, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
		task_offset: int = 0,
		task_total: int | None = None,
	):
		del progress, task, task_offset, task_total
		calls.append(f"install:{options.prefix}")
		if status is not None:
			status("Install complete.")
		return InstallManifest(
			version="1.6.0",
			prefix=str(options.prefix),
			installed_at="2026-08-03T12:00:00+00:00",
		)

	monkeypatch.setattr(controller_mod, "uninstall_prefix", fake_uninstall)
	monkeypatch.setattr(controller_mod, "install_srxy", fake_install)
	controller = InstallerController()
	controller.setMode("reinstall")
	controller.setPrivacyAck(True)
	controller.setPrefix(str(prefix))

	# when
	controller.startReinstall()
	deadline = time.monotonic() + 2.0
	while time.monotonic() < deadline:
		QCoreApplication.processEvents()
		if bool(controller.busy) and "uninstall:" in "".join(calls):
			break
		time.sleep(0.01)
	assert bool(controller.busy) is True
	assert str(controller.page) == "progress"
	release.set()
	deadline = time.monotonic() + 5.0
	while bool(controller.busy) and time.monotonic() < deadline:
		QCoreApplication.processEvents()
		time.sleep(0.01)

	# then
	assert calls == [f"uninstall:{prefix.resolve()}", f"install:{prefix.resolve()}"]
	assert bool(controller.finished) is True
	assert bool(controller.busy) is False
	assert cast(float, controller.progressValue) == 1.0
	assert controller.wait_for_worker_for_tests()
	QCoreApplication.processEvents()


def test_given_install_mode_when_starting_then_does_not_call_uninstall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given — install-or-update must not wipe via uninstall_prefix
	import time
	from collections.abc import Callable

	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer import controller as controller_mod
	from srxy.adapters.inbound.installer.controller import InstallerController
	from srxy.adapters.inbound.installer.install import InstallOptions

	if QCoreApplication.instance() is None:
		QCoreApplication([])

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	write_manifest(
		prefix,
		InstallManifest(version="1.5.0", prefix=str(prefix), installed_at="2026-08-02T12:00:00+00:00"),
	)
	calls: list[str] = []

	def boom_uninstall(*_args: object, **_kwargs: object):
		calls.append("uninstall")
		raise AssertionError("install-or-update must not uninstall")

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int, int, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
		task_offset: int = 0,
		task_total: int | None = None,
	):
		del progress, task, task_offset, task_total
		calls.append("install")
		if status is not None:
			status("Install complete.")
		return InstallManifest(
			version="1.6.0",
			prefix=str(options.prefix),
			installed_at="2026-08-03T12:00:00+00:00",
		)

	monkeypatch.setattr(controller_mod, "uninstall_prefix", boom_uninstall)
	monkeypatch.setattr(controller_mod, "install_srxy", fake_install)
	controller = InstallerController()
	controller.setMode("install")
	controller.setPrivacyAck(True)
	controller.setPrefix(str(prefix))

	# when
	controller.startInstall()
	deadline = time.monotonic() + 5.0
	while bool(controller.busy) and time.monotonic() < deadline:
		QCoreApplication.processEvents()
		time.sleep(0.01)

	# then
	assert calls == ["install"]
	assert bool(controller.finished) is True
	assert controller.wait_for_worker_for_tests()
	QCoreApplication.processEvents()


def test_given_non_empty_foreign_dir_when_checking_then_flags_foreign(tmp_path: Path):
	# given
	foreign = tmp_path / "foreign"
	foreign.mkdir()
	(foreign / "notes.txt").write_text("hello", encoding="utf-8")

	# when / then
	assert is_non_empty_foreign_prefix(foreign) is True


def test_given_matching_manifest_when_requiring_then_returns_manifest(tmp_path: Path):
	# given
	manifest = InstallManifest(
		version="1.5.0",
		prefix=str(tmp_path),
		installed_at="2026-08-02T12:00:00+00:00",
	)
	write_manifest(tmp_path, manifest)

	# when
	loaded = require_matching_manifest(tmp_path)

	# then
	assert loaded.prefix == str(tmp_path)


@pytest.mark.skipif(platform.system().lower() == "windows", reason="Unix shell launcher")
def test_given_prefix_when_writing_launcher_then_tty_branch_and_quoted_paths_exist(tmp_path: Path):
	# given
	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / ".venv" / "bin").mkdir(parents=True)
	(prefix / ".venv" / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	# when
	write_launcher(prefix)
	content = (prefix / "bin" / "srxy").read_text(encoding="utf-8")

	# then
	assert "[ -t 1 ]" in content
	assert "exec " in content
	assert '>>"$LOG_FILE" 2>&1' in content
	assert 'echo "argv: $*"' not in content or "SRXY_DEBUG:-" in content
	assert "Applications/srxy" in content or "Applications\\/srxy" in content
	assert 'exec ">>"$LOG_FILE"' not in content.replace("\n", " ")


@pytest.mark.skipif(platform.system().lower() == "windows", reason="Unix shell launcher")
def test_given_prefix_when_writing_launcher_then_no_unconditional_redirect_before_tty_check(
	tmp_path: Path,
):
	# given
	prefix = tmp_path / "srxy"
	prefix.mkdir()
	(prefix / ".venv" / "bin").mkdir(parents=True)
	(prefix / ".venv" / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	# when
	write_launcher(prefix)
	text = (prefix / "bin" / "srxy").read_text(encoding="utf-8")

	# then
	tty_index = text.index("[ -t 1 ]")
	redirect_index = text.index('>>"$LOG_FILE" 2>&1')
	assert tty_index < redirect_index
	tty_branch = text.split("else", 1)[0]
	assert '>>"$LOG_FILE" 2>&1' not in tty_branch


def test_given_darwin_when_writing_launcher_then_creates_srxy_app_bundle(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.adapters.inbound.installer import install as install_mod

	monkeypatch.setattr(install_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(install_mod.shutil, "which", lambda _name: None)
	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / ".venv" / "bin").mkdir(parents=True)
	(prefix / ".venv" / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	# when
	write_launcher(prefix)

	# then
	app_exe = prefix / "Srxy.app" / "Contents" / "MacOS" / "srxy"
	assert app_exe.is_file()
	assert "SRXY_HOME=" in app_exe.read_text(encoding="utf-8")
	assert (prefix / "Srxy.app" / "Contents" / "Info.plist").is_file()


def test_given_windows_prefix_when_writing_launcher_then_writes_cmd(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer import install as install_mod

	monkeypatch.setattr(install_mod.platform, "system", lambda: "Windows")
	monkeypatch.setattr(install_mod, "_write_windows_gui_exe", lambda _prefix: None)
	prefix = tmp_path / "Programs" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / ".venv" / "Scripts").mkdir(parents=True)
	(prefix / ".venv" / "Scripts" / "srxy.exe").write_bytes(b"")

	# when
	write_launcher(prefix)

	# then
	cmd = prefix / "bin" / "srxy.cmd"
	assert cmd.is_file()
	text = cmd.read_text(encoding="utf-8")
	assert "SRXY_HOME=" in text
	assert "srxy.exe" in text
	assert "TESSDATA_PREFIX" in text


@pytest.mark.skipif(platform.system().lower() != "windows", reason="requires csc.exe")
def test_given_windows_prefix_when_writing_launcher_then_builds_gui_exe(
	tmp_path: Path,
):
	# given
	prefix = tmp_path / "Programs" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / ".venv" / "Scripts").mkdir(parents=True)
	(prefix / ".venv" / "Scripts" / "srxy.exe").write_bytes(b"")
	(prefix / ".venv" / "Scripts" / "pythonw.exe").write_bytes(b"")

	# when
	write_launcher(prefix)

	# then
	gui = prefix / "bin" / "Srxy.exe"
	assert gui.is_file()
	assert gui.stat().st_size > 0
	assert (prefix / "share" / "icons" / "srxy.ico").is_file()
	assert (prefix / "bin" / "srxy.cmd").is_file()


def test_given_default_options_when_planning_phases_then_includes_vendor_and_path(tmp_path: Path):
	# given
	from srxy.adapters.inbound.installer.install import InstallOptions, plan_install_phases

	options = InstallOptions(
		prefix=tmp_path / "srxy",
		download_tesseract=True,
		download_ffmpeg=True,
		install_semantic=False,
		prefetch_models=False,
		add_to_path=True,
	)

	# when
	keys = [phase.key for phase in plan_install_phases(options)]

	# then
	assert keys == ["uv", "venv", "package", "tesseract", "ffmpeg", "launcher", "path"]


def test_given_minimal_options_when_planning_phases_then_skips_optional_steps(tmp_path: Path):
	# given
	from srxy.adapters.inbound.installer.install import InstallOptions, plan_install_phases

	options = InstallOptions(
		prefix=tmp_path / "srxy",
		download_tesseract=False,
		download_ffmpeg=False,
		install_semantic=False,
		prefetch_models=False,
		add_to_path=False,
	)

	# when
	keys = [phase.key for phase in plan_install_phases(options)]

	# then
	assert keys == ["uv", "venv", "package", "launcher"]


def test_given_task_and_download_progress_when_installing_then_exposes_dual_bars(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	import os
	import time
	from collections.abc import Callable
	from typing import cast

	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer import controller as controller_mod
	from srxy.adapters.inbound.installer.controller import InstallerController
	from srxy.adapters.inbound.installer.install import InstallOptions
	from srxy.adapters.inbound.installer.manifest import InstallManifest

	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	if QCoreApplication.instance() is None:
		QCoreApplication([])

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int, int, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
		task_offset: int = 0,
		task_total: int | None = None,
	) -> InstallManifest:
		del task_offset, task_total
		if task is not None:
			task(2, 4, "Downloading ffmpeg…")
		if progress is not None:
			# Multi-GB byte counts used to overflow Signal(int, int, str).
			progress(1_925_000_000, 3_850_000_000, "ffmpeg 7.0")
		if status is not None:
			status("Downloading ffmpeg…")
		return InstallManifest(
			version="1.6.0",
			prefix=str(options.prefix),
			installed_at="2026-08-03T12:00:00+00:00",
		)

	monkeypatch.setattr(controller_mod, "install_srxy", fake_install)
	controller = InstallerController()
	controller.setPrivacyAck(True)
	controller.setPrefix(str(prefix))

	# when
	controller.startInstall()
	deadline = time.monotonic() + 5.0
	while bool(controller.busy) and time.monotonic() < deadline:
		QCoreApplication.processEvents()
		time.sleep(0.01)
	controller.shutdown()

	# then
	assert bool(controller.finished) is True
	assert bool(controller.canGoBack) is False
	assert "Install complete" in str(controller.status)
	assert str(controller.progressLabel) == ""
	assert cast(float, controller.overallProgressValue) == 1.0
	assert "4 / 4" in str(controller.overallProgressText) or "100%" in str(controller.overallProgressText)
	controller.goBack()
	assert str(controller.page) == "progress"


def test_given_multi_gb_bytes_when_updating_progress_then_shows_human_sizes(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	import os
	import time
	from collections.abc import Callable

	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer import controller as controller_mod
	from srxy.adapters.inbound.installer.controller import InstallerController
	from srxy.adapters.inbound.installer.install import InstallOptions
	from srxy.adapters.inbound.installer.manifest import InstallManifest

	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	if QCoreApplication.instance() is None:
		QCoreApplication([])

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)

	mid: dict[str, object] = {}

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int | float, int | float, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
		task_offset: int = 0,
		task_total: int | None = None,
	) -> InstallManifest:
		del task_offset, task_total
		if task is not None:
			task(2, 4, "Downloading ffmpeg…")
		if progress is not None:
			progress(1_925_000_000, 3_850_000_000, "ffmpeg 7.0")
		# Hold the worker so the UI thread can sample mid-download state.
		deadline = time.monotonic() + 2.0
		while time.monotonic() < deadline and not mid.get("sampled"):
			time.sleep(0.01)
		if status is not None:
			status("Downloading ffmpeg…")
		return InstallManifest(
			version="1.6.0",
			prefix=str(options.prefix),
			installed_at="2026-08-03T12:00:00+00:00",
		)

	monkeypatch.setattr(controller_mod, "install_srxy", fake_install)
	controller = InstallerController()
	controller.setPrivacyAck(True)
	controller.setPrefix(str(prefix))

	# when
	controller.startInstall()
	deadline = time.monotonic() + 5.0
	while bool(controller.busy) and time.monotonic() < deadline:
		QCoreApplication.processEvents()
		task_text = str(controller.taskProgressText)
		if "GB" in task_text and not mid.get("sampled"):
			mid["sampled"] = True
			mid["status"] = str(controller.status)
			mid["progress_label"] = str(controller.progressLabel)
			mid["task_text"] = task_text
			mid["progress_value"] = float(controller.progressValue)  # pyright: ignore[reportArgumentType]
		time.sleep(0.01)
	controller.shutdown()

	# then — phase stays human; task bar shows GB, not raw byte counts / vendor names
	assert mid.get("sampled") is True
	assert "Downloading ffmpeg" in str(mid["status"])
	assert mid["progress_label"] == ""
	assert "GB" in str(mid["task_text"])
	assert "ffmpeg" not in str(mid["task_text"])
	progress_value = mid["progress_value"]
	assert isinstance(progress_value, float)
	assert progress_value == pytest.approx(0.5, abs=0.01)
	assert bool(controller.finished) is True


def test_given_progress_line_when_parsing_then_extracts_done_total_label():
	# given
	from srxy.adapters.outbound.models.model_store import format_progress_line, parse_progress_line

	# when
	line = format_progress_line(12, 100, "model.bin")
	parsed = parse_progress_line(line)

	# then
	assert parsed == (12, 100, "model.bin")
	assert parse_progress_line("noise") is None


def test_given_prefix_with_launcher_when_launching_installed_app_then_spawns_detached(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.adapters.inbound.installer import launch_app

	prefix = tmp_path / "Applications" / "srxy"
	bin_dir = prefix / "bin"
	bin_dir.mkdir(parents=True)
	launcher = bin_dir / "srxy"
	launcher.write_text("#!/bin/sh\n", encoding="utf-8")
	launcher.chmod(0o755)
	seen: list[list[str]] = []

	def fake_popen(cmd: list[str], **kwargs: object):
		seen.append(list(cmd))
		assert kwargs.get("start_new_session") is True
		return object()

	monkeypatch.setattr(launch_app.platform, "system", lambda: "Linux")
	monkeypatch.setattr(launch_app.subprocess, "Popen", fake_popen)

	# when
	launch_app.launch_installed_app(prefix)

	# then
	assert seen == [[str(launcher.resolve())]]


def test_given_darwin_app_bundle_when_launching_then_uses_open(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	from srxy.adapters.inbound.installer import launch_app

	prefix = tmp_path / "Applications" / "srxy"
	app_exe = prefix / "Srxy.app" / "Contents" / "MacOS" / "srxy"
	app_exe.parent.mkdir(parents=True)
	app_exe.write_text("#!/bin/sh\n", encoding="utf-8")
	app_exe.chmod(0o755)
	seen: list[list[str]] = []

	def fake_popen(cmd: list[str], **kwargs: object):
		seen.append(list(cmd))
		return object()

	monkeypatch.setattr(launch_app.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(launch_app.shutil, "which", lambda _name: "/usr/bin/open")
	monkeypatch.setattr(launch_app.subprocess, "Popen", fake_popen)

	launch_app.launch_installed_app(prefix)

	assert seen == [["/usr/bin/open", str((prefix / "Srxy.app").resolve())]]


def test_given_finished_install_when_launch_installed_then_starts_app_and_quits(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from PySide6.QtCore import QCoreApplication

	from srxy.adapters.inbound.installer import controller as controller_mod
	from srxy.adapters.inbound.installer.controller import InstallerController

	if QCoreApplication.instance() is None:
		QCoreApplication([])

	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	prefix = home / "Applications" / "srxy"
	bin_dir = prefix / "bin"
	bin_dir.mkdir(parents=True)
	(bin_dir / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")
	launched: list[str] = []
	quit_calls: list[int] = []
	timer_ms: list[int] = []

	monkeypatch.setattr(
		controller_mod,
		"launch_installed_app",
		lambda path: launched.append(str(path)),
	)
	monkeypatch.setattr(
		controller_mod.QTimer,
		"singleShot",
		lambda ms, cb: (timer_ms.append(int(ms)), cb()),
	)
	monkeypatch.setattr(controller_mod.QCoreApplication, "quit", lambda: quit_calls.append(1))

	controller = InstallerController()
	controller.setPrefix(str(prefix))
	controller._finished = True  # pyright: ignore[reportPrivateUsage]
	controller._mode = "install"  # pyright: ignore[reportPrivateUsage]

	# when
	controller.launchInstalled()

	# then
	assert launched == [str(prefix)]
	assert timer_ms == [int(controller_mod.LAUNCH_TEARDOWN_DELAY_SECONDS * 1000)]
	assert quit_calls == [1]
