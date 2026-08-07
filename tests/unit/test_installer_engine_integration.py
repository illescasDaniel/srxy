"""Installer engine integration tests (mocked network; no semantic models).

Kept under ``tests/unit/`` so ``tests/integration/conftest.py`` session fixtures
(semantic models) do not apply. Marked ``integration`` for the local serial gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.__main__ import main
from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION
from srxy.i18n import get_language, set_language, tr


pytestmark = pytest.mark.integration


def test_given_english_inno_install_when_headless_then_progress_matches_language(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	set_language("es")  # OS-like default; --language must override
	statuses: list[str] = []

	def fake_install(options: object, **kwargs: object):
		_ = options
		statuses.append(get_language())
		status = kwargs.get("status")
		progress = kwargs.get("progress")
		task = kwargs.get("task")
		# Simulate the STATUS/TASK/PROGRESS protocol the Inno wizard consumes.
		label = tr("installer.status.installing_uv")
		if callable(status):
			status(label)
		if callable(task):
			task(1, 7, label)
		if callable(progress):
			progress(1, 1, label)
		label_ff = tr("installer.status.downloading_ffmpeg")
		if callable(status):
			status(label_ff)
		if callable(task):
			task(5, 7, label_ff)

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.install.install_srxy",
		fake_install,
	)

	code = main(
		[
			"--install",
			"--prefix",
			str(tmp_path / "srxy"),
			"--privacy-ack",
			PRIVACY_NOTICE_VERSION,
			"--language",
			"en",
			"--ffmpeg",
			"--confirm-unsafe",
			"--no-add-path",
		]
	)

	assert code == 0
	assert statuses == ["en"]
	out = capsys.readouterr().out
	assert "STATUS\tInstalling uv..." in out
	assert "TASK\t1\t7\tInstalling uv..." in out
	assert "STATUS\tDownloading ffmpeg..." in out
	assert "TASK\t5\t7\tDownloading ffmpeg..." in out
	assert "Instalando" not in out
	assert "Descargando" not in out
	assert "\u2026" not in out
	assert "OK\tinstall" in out


def test_given_spanish_inno_install_when_headless_then_progress_is_spanish_ascii(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	set_language("en")

	def fake_install(options: object, **kwargs: object):
		_ = options
		status = kwargs.get("status")
		task = kwargs.get("task")
		label = tr("installer.status.downloading_ffmpeg")
		if callable(status):
			status(label)
		if callable(task):
			task(5, 7, label)

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.install.install_srxy",
		fake_install,
	)

	code = main(
		[
			"--install",
			"--prefix",
			str(tmp_path / "srxy"),
			"--privacy-ack",
			PRIVACY_NOTICE_VERSION,
			"--language",
			"es",
			"--confirm-unsafe",
			"--no-add-path",
		]
	)

	assert code == 0
	out = capsys.readouterr().out
	assert "STATUS\tDescargando ffmpeg..." in out
	assert "TASK\t5\t7\tDescargando ffmpeg..." in out
	assert "Downloading ffmpeg" not in out
	assert "\u2026" not in out
