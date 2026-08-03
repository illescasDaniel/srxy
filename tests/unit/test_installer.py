from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.helpers import set_fake_home

from srxy.adapters.inbound.installer.install import write_launcher
from srxy.adapters.inbound.installer.manifest import (
	InstallManifest,
	is_non_empty_foreign_prefix,
	is_srxy_prefix,
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


def test_given_spanish_when_loading_privacy_then_translates_prose():
	# given
	from srxy.i18n import set_language

	set_language("es")

	# when
	text = privacy_disclaimer_text()
	html = privacy_disclaimer_html()
	app_html = privacy_disclaimer_html(for_app=True)

	# then
	assert "aviso de privacidad" in text.lower()
	assert "terceros" in text.lower()
	assert "Sitio:" in text or "Sitio:" in html
	assert "Privacidad:" in text or "Privacidad:" in html
	assert "https://huggingface.co/privacy" in html
	assert "instalador de escritorio de srxy" in html.lower()
	assert "este instalador" in html.lower()
	assert "este appimage" in html.lower() or "este AppImage".lower() in html.lower()
	assert "instalador de escritorio de srxy" not in app_html.lower()
	assert "este instalador" not in app_html.lower()
	assert "este appimage" not in app_html.lower()
	assert "qué puede descargar srxy" in app_html.lower()
	assert "srxy — aviso" in app_html.lower()
	assert "casilla de aceptación" not in app_html.lower()
	set_language("en")
	app_en = privacy_disclaimer_html(for_app=True)
	assert "this installer" not in app_en.lower()
	assert "this appimage" not in app_en.lower()
	assert "what srxy may download" in app_en.lower()
	assert "acknowledgment box" not in app_en.lower()


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


def test_given_bin_srxy_only_when_checking_prefix_then_rejects(tmp_path: Path):
	# given
	(tmp_path / "bin").mkdir()
	(tmp_path / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	# when / then
	assert is_srxy_prefix(tmp_path) is False


def test_given_bin_srxy_only_when_uninstalling_then_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	home = tmp_path / "home"
	home.mkdir()
	prefix = home / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / "bin").mkdir()
	(prefix / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")
	set_fake_home(monkeypatch, home)

	# when / then
	with pytest.raises(RuntimeError, match=MANIFEST_NAME):
		uninstall_prefix(prefix)


def test_given_prefix_mismatch_when_uninstalling_then_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	write_manifest(
		prefix,
		InstallManifest(version="1.5.0", prefix=str(tmp_path / "other"), installed_at="2026-08-02T12:00:00+00:00"),
	)
	set_fake_home(monkeypatch, tmp_path)

	# when / then
	with pytest.raises(RuntimeError, match="does not match"):
		uninstall_prefix(prefix)


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
	) -> InstallManifest:
		captured["confirm_unsafe"] = options.confirm_unsafe
		captured["prefix"] = options.prefix
		if status is not None:
			status("ok")
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
