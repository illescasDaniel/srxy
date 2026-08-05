from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.adapters.inbound.installer.__main__ import main
from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION


pytestmark = pytest.mark.unit


def test_given_help_flag_when_running_installer_main_then_exits_zero_without_gui(
	capsys: pytest.CaptureFixture[str],
):
	# given / when
	with pytest.raises(SystemExit) as exc:
		main(["--help"])

	# then
	assert exc.value.code == 0
	assert "Install or uninstall srxy" in capsys.readouterr().out


def test_given_version_flag_when_running_installer_main_then_prints_version(
	capsys: pytest.CaptureFixture[str],
):
	# given / when
	code = main(["--version"])

	# then
	assert code == 0
	assert capsys.readouterr().out.strip()


def test_given_install_without_privacy_ack_when_headless_then_errors(
	capsys: pytest.CaptureFixture[str],
	tmp_path: Path,
):
	# given / when
	code = main(["--install", "--prefix", str(tmp_path / "srxy")])

	# then
	assert code == 1
	err = capsys.readouterr()
	assert "privacy acknowledgment" in err.err.lower() or "privacy acknowledgment" in err.out.lower()
	assert "ERROR" in err.out


def test_given_headless_install_when_invoked_then_calls_install_srxy(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	# given
	called: dict[str, object] = {}

	def fake_install(options, **kwargs):
		called["options"] = options
		called["kwargs"] = kwargs
		return MagicMock()

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.install.install_srxy",
		fake_install,
	)

	# when
	code = main(
		[
			"--install",
			"--prefix",
			str(tmp_path / "srxy"),
			"--privacy-ack",
			PRIVACY_NOTICE_VERSION,
			"--tesseract",
			"--no-add-path",
			"--confirm-unsafe",
		]
	)

	# then
	assert code == 0
	options = called["options"]
	assert options.prefix == tmp_path / "srxy"
	assert options.download_tesseract is True
	assert options.download_ffmpeg is False
	assert options.add_to_path is False
	assert options.confirm_unsafe is True
	out = capsys.readouterr().out
	assert "OK\tinstall" in out


def test_given_headless_uninstall_when_invoked_then_calls_uninstall_prefix(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	# given
	seen: list[Path] = []

	def fake_uninstall(prefix, **kwargs):
		seen.append(prefix)

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.uninstall.uninstall_prefix",
		fake_uninstall,
	)

	# when
	code = main(["--uninstall", "--prefix", str(tmp_path / "gone"), "--confirm-unsafe"])

	# then
	assert code == 0
	assert seen == [tmp_path / "gone"]
	assert "OK\tuninstall" in capsys.readouterr().out
