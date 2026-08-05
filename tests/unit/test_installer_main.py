from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.adapters.inbound.installer.__main__ import main
from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION


pytestmark = pytest.mark.unit

_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
_UPDATE_SNAPSHOTS = os.environ.get("UPDATE_INSTALLER_SNAPSHOTS", "").strip().lower() in {
	"1",
	"true",
	"yes",
}


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

	def fake_install(options: object, **kwargs: object):
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

	def fake_uninstall(prefix: Path, **kwargs: object):
		seen.append(prefix)
		status = kwargs.get("status")
		if callable(status):
			status("removing")

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.uninstall.uninstall_prefix",
		fake_uninstall,
	)

	# when
	code = main(["--uninstall", "--prefix", str(tmp_path / "gone"), "--confirm-unsafe"])

	# then
	assert code == 0
	assert seen == [tmp_path / "gone"]
	out = capsys.readouterr().out
	assert "OK\tuninstall" in out
	assert "TASK\t1\t2\t" in out
	assert "TASK\t2\t2\t" in out
	assert "STATUS\t" in out


def test_given_language_flag_when_headless_then_sets_i18n(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	from srxy.i18n import get_language, set_language

	set_language("en")
	seen: list[str] = []

	def fake_uninstall(prefix: Path, **kwargs: object):
		_ = prefix, kwargs
		seen.append(get_language())

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.uninstall.uninstall_prefix",
		fake_uninstall,
	)

	code = main(["--uninstall", "--prefix", str(tmp_path / "gone"), "--confirm-unsafe", "--language", "es"])

	assert code == 0
	assert seen == ["es"]
	assert "\u2026" not in capsys.readouterr().out


def test_given_language_flag_when_headless_install_then_sets_i18n(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	from srxy.i18n import get_language, set_language

	set_language("en")
	seen: list[str] = []

	def fake_install(options: object, **kwargs: object):
		_ = options, kwargs
		seen.append(get_language())
		return MagicMock()

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
			"english",
			"--confirm-unsafe",
			"--no-add-path",
		]
	)

	assert code == 0
	assert seen == ["en"]
	assert "OK\tinstall" in capsys.readouterr().out


def test_given_inno_spanish_language_name_when_headless_then_maps_to_es(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	from srxy.i18n import get_language, set_language

	set_language("en")
	seen: list[str] = []

	def fake_uninstall(prefix: Path, **kwargs: object):
		_ = prefix, kwargs
		seen.append(get_language())

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.uninstall.uninstall_prefix",
		fake_uninstall,
	)

	code = main(["--uninstall", "--prefix", str(tmp_path / "gone"), "--confirm-unsafe", "--language", "spanish"])

	assert code == 0
	assert seen == ["es"]


def test_given_ellipsis_status_when_emitting_then_uses_ascii_dots(
	capsys: pytest.CaptureFixture[str],
):
	from srxy.adapters.inbound.installer import __main__ as installer_main

	installer_main._emit("STATUS", "Installing uv\u2026")  # pyright: ignore[reportPrivateUsage]
	assert "STATUS\tInstalling uv..." in capsys.readouterr().out


def test_given_ellipsis_in_progress_and_task_when_emitting_then_uses_ascii_dots(
	capsys: pytest.CaptureFixture[str],
):
	from srxy.adapters.inbound.installer import __main__ as installer_main

	installer_main._emit("PROGRESS", 1, 2, "Descargando ffmpeg\u2026")  # pyright: ignore[reportPrivateUsage]
	installer_main._emit("TASK", 5, 7, "Instalando uv\u2026")  # pyright: ignore[reportPrivateUsage]
	installer_main._emit("ERROR", "failed\u2026")  # pyright: ignore[reportPrivateUsage]
	out = capsys.readouterr().out
	assert "PROGRESS\t1\t2\tDescargando ffmpeg..." in out
	assert "TASK\t5\t7\tInstalando uv..." in out
	assert "ERROR\tfailed..." in out
	assert "\u2026" not in out


def test_given_accented_spanish_when_emitting_then_output_is_ascii_safe(
	capsys: pytest.CaptureFixture[str],
):
	"""Diamond-question glyphs must not appear in Inno's ANSI progress pipe.

	Accented characters (ñ, á, é, etc.) must be transliterated to their plain
	ASCII base letters so the Inno Setup ExecAndLogOutput callback receives a
	valid ASCII byte sequence regardless of the Windows code page.
	"""
	from srxy.adapters.inbound.installer import __main__ as installer_main

	# Spanish strings that appear near the end of installation
	installer_main._emit("STATUS", "A\u00f1adiendo acceso directo al PATH...")  # pyright: ignore[reportPrivateUsage]
	installer_main._emit("STATUS", "Instalando srxy\u2026")  # pyright: ignore[reportPrivateUsage]
	installer_main._emit("STATUS", "Descargando Tesseract\u2026")  # pyright: ignore[reportPrivateUsage]
	out = capsys.readouterr().out
	assert out.isascii(), f"Non-ASCII bytes in engine output:\n{out!r}"
	# Accents stripped, not replaced with '?'
	assert "Anadiendo" in out
	assert "Instalando srxy..." in out
	assert "Descargando Tesseract..." in out


def test_given_progress_text_helper_when_called_with_unicode_then_returns_ascii(
	capsys: pytest.CaptureFixture[str],  # noqa: ARG001
):
	from srxy.adapters.inbound.installer import __main__ as installer_main

	# Plain ASCII passthrough
	assert installer_main._progress_text("hello") == "hello"  # pyright: ignore[reportPrivateUsage]
	# Ellipsis stripped
	assert installer_main._progress_text("done\u2026") == "done..."  # pyright: ignore[reportPrivateUsage]
	# Accented letters transliterated
	assert installer_main._progress_text("A\u00f1adiendo") == "Anadiendo"  # pyright: ignore[reportPrivateUsage]
	assert installer_main._progress_text("Instalaci\u00f3n") == "Instalacion"  # pyright: ignore[reportPrivateUsage]
	# Full Spanish phrase — result must be ASCII
	result = installer_main._progress_text("Ejecutando el motor de instalaci\u00f3n...")  # pyright: ignore[reportPrivateUsage]
	assert result.isascii()


def test_given_spanish_uninstall_when_headless_then_progress_snapshot(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	from srxy.i18n import set_language

	set_language("en")

	def fake_uninstall(prefix: Path, **kwargs: object):
		_ = prefix, kwargs

	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.uninstall.uninstall_prefix",
		fake_uninstall,
	)

	code = main(["--uninstall", "--prefix", str(tmp_path / "gone"), "--confirm-unsafe", "--language", "es"])
	assert code == 0
	out = capsys.readouterr().out
	assert "\u2026" not in out
	assert "Quitando la app srxy..." in out

	lines = [line for line in out.splitlines() if line.startswith(("STATUS\t", "TASK\t", "PROGRESS\t", "OK\t"))]
	tree = "\n".join(lines) + "\n"
	snap = _SNAPSHOTS / "installer_progress_uninstall_es.snap.txt"
	if _UPDATE_SNAPSHOTS or not snap.is_file():
		snap.parent.mkdir(parents=True, exist_ok=True)
		snap.write_text(tree, encoding="utf-8")
	assert snap.read_text(encoding="utf-8") == tree
