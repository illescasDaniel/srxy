"""macOS .app launcher source packaging + LaunchServices smoke."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from srxy.resources.macos import app_launcher_c_path


def test_given_package_when_resolving_app_launcher_c_then_source_exists():
	path = app_launcher_c_path()
	assert path.is_file()
	text = path.read_text(encoding="utf-8")
	assert "SrxyPython" in text
	assert "_NSGetExecutablePath" in text
	assert "SRXY_HOME_PATH" in text
	assert "SRXY_PYTHONHOME" in text
	assert 'setenv("PYTHONHOME"' in text


def test_given_package_when_resolving_installer_launcher_c_then_source_exists():
	from srxy.resources.macos import installer_launcher_c_path

	path = installer_launcher_c_path()
	assert path.is_file()
	text = path.read_text(encoding="utf-8")
	assert "_NSGetExecutablePath" in text
	assert "APPDIR" in text
	assert "srxy.adapters.inbound.installer" in text
	assert "Resources/venv/bin/python" in text


def test_given_repair_script_when_rewriting_launcher_then_uses_env_path_not_unquoted_path():
	"""Regression: ``Path($(printf '%q' …))`` produced ``Path(/Users/…)`` SyntaxError."""
	script = Path(__file__).resolve().parents[2] / "scripts" / "macos" / "repair-prefix-gui.sh"
	text = script.read_text(encoding="utf-8")
	assert "Path($(printf" not in text
	assert 'Path(os.environ["SRXY_HOME"])' in text
	assert "<<'PY'" in text
	assert "vtool" in text
	assert "sdk 26" in text
	assert "hardlink" in text


@pytest.mark.skipif(platform.system().lower() != "darwin", reason="vtool / Mach-O only on macOS")
def test_given_macho_python_when_restamping_sdk_then_lc_build_version_is_26(tmp_path: Path):
	from srxy.adapters.inbound.installer.install import (
		_adhoc_codesign_macos,
		_is_macho_executable,
		_restamp_macos_linked_sdk,
	)

	src = Path(sys.executable).resolve()
	if not _is_macho_executable(src):
		pytest.skip(f"sys.executable is not Mach-O: {src}")
	dest = tmp_path / "SrxyPython"
	shutil.copy2(src, dest)
	dest.chmod(0o755)
	assert _restamp_macos_linked_sdk(dest) is True
	_adhoc_codesign_macos(dest)
	show = subprocess.check_output(["/usr/bin/vtool", "-show-build", str(dest)], text=True)  # noqa: S603
	assert re.search(r"sdk\s+26(\.|$|\s)", show), show
	assert re.search(r"minos\s+12(\.|$|\s)", show), show
	# Must not share inode with the source (copy, not hardlink).
	assert dest.stat().st_ino != src.stat().st_ino


@pytest.mark.skipif(platform.system().lower() != "darwin", reason="LaunchServices only on macOS")
def test_given_macho_bundle_when_open_then_not_missing_executable(tmp_path: Path):
	"""Isolated from GUI Qt process — shell CFBundleExecutable caused Dock '(null)'."""
	from srxy.adapters.inbound.installer.install import write_launcher

	prefix = tmp_path / "Applications" / "srxy"
	(prefix / ".venv" / "bin").mkdir(parents=True)
	(prefix / ".venv" / "bin" / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")
	fake_home = tmp_path / "fake-python-home"
	fake_home.mkdir()
	fake_py = prefix / ".venv" / "bin" / "python"
	# Probe script used by _venv_python_home; also used as the embedded interpreter.
	fake_py.write_text(
		"#!/bin/sh\n"
		'for arg in "$@"; do\n'
		'	case "$arg" in\n'
		"		*base_prefix*) echo '" + fake_home.as_posix() + "'; exit 0 ;;\n"
		"	esac\n"
		"done\n"
		"exit 0\n",
		encoding="utf-8",
	)
	fake_py.chmod(0o755)
	(prefix / ".venv" / "lib" / "python3.12" / "site-packages").mkdir(parents=True)

	write_launcher(prefix)
	app = prefix / "Srxy.app"
	exe = app / "Contents" / "MacOS" / "srxy"
	assert exe.read_bytes()[:4] in {
		b"\xcf\xfa\xed\xfe",
		b"\xfe\xed\xfa\xcf",
		b"\xca\xfe\xba\xbe",
		b"\xbe\xba\xfe\xca",
	}
	# Relocated SrxyPython needs PYTHONHOME baked into the Mach-O launcher.
	strings_out = subprocess.check_output(["/usr/bin/strings", str(exe)], text=True)  # noqa: S603
	assert fake_home.as_posix() in strings_out
	# Shell stub is copied (not restamped) — still present as SrxyPython.
	assert (app / "Contents" / "MacOS" / "SrxyPython").is_file()
	assert os.access(exe, os.X_OK)
	# LaunchServices often refuses unsigned apps under /var/folders on Tahoe
	# (kLSNoExecutableErr) even when the Mach-O is valid — assert direct exec instead.
	direct = subprocess.run(  # noqa: S603
		[str(exe), "--help"],
		check=False,
		capture_output=True,
		text=True,
	)
	assert direct.returncode == 0, (direct.stdout or "") + (direct.stderr or "")


@pytest.mark.skipif(platform.system().lower() != "darwin", reason="embed restamp only on macOS")
def test_given_real_venv_python_when_write_launcher_then_embedded_sdk_is_26(tmp_path: Path):
	"""Installed SrxyPython must be a restamped copy so AppKit enables Liquid Glass."""
	from srxy.adapters.inbound.installer.install import _is_macho_executable, write_launcher

	real_py = Path(sys.executable).resolve()
	if not _is_macho_executable(real_py):
		pytest.skip(f"sys.executable is not Mach-O: {real_py}")

	prefix = tmp_path / "Applications" / "srxy"
	bin_dir = prefix / ".venv" / "bin"
	bin_dir.mkdir(parents=True)
	(bin_dir / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")
	# Point venv python at the real interpreter (symlink) so embed copies a Mach-O.
	(bin_dir / "python").symlink_to(real_py)
	site = prefix / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
	site.mkdir(parents=True)

	write_launcher(prefix)
	embedded = prefix / "Srxy.app" / "Contents" / "MacOS" / "SrxyPython"
	assert embedded.is_file()
	assert embedded.stat().st_ino != real_py.stat().st_ino
	show = subprocess.check_output(["/usr/bin/vtool", "-show-build", str(embedded)], text=True)  # noqa: S603
	assert re.search(r"sdk\s+26(\.|$|\s)", show), show


@pytest.mark.skipif(platform.system() not in {"Linux", "Darwin"}, reason="Unix C launcher probe")
@pytest.mark.parametrize("argument_count", [3, 59, 60])
def test_given_app_launcher_when_forwarding_arguments_then_marker_and_capacity_are_safe(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	argument_count: int,
):
	# given — Linux substitutes only the dyld executable-location API; the real
	# packaged launcher source, argv allocation and execv all execute unchanged.
	clang = shutil.which("clang")
	if clang is None:
		pytest.skip("clang unavailable")
	app_dir = tmp_path / "Srxy café # 100%.app/Contents/MacOS"
	app_dir.mkdir(parents=True)
	probe = app_dir / "SrxyPython"
	probe.write_text(
		'#!/bin/sh\nprintf "%s\\0" "$PWD" "$@" > "$SRXY_STARTUP_PROBE"\n',
		encoding="utf-8",
	)
	probe.chmod(0o755)
	record = tmp_path / "argv.bin"
	monkeypatch.setenv("SRXY_STARTUP_PROBE", str(record))
	include: list[str] = []
	if platform.system() == "Linux":
		header = tmp_path / "include/mach-o/dyld.h"
		header.parent.mkdir(parents=True)
		header.write_text(
			"#include <stdint.h>\n#include <unistd.h>\n"
			"static int _NSGetExecutablePath(char *buf, uint32_t *size) {\n"
			' ssize_t n = readlink("/proc/self/exe", buf, *size - 1);\n'
			" if (n < 0) return -1; buf[n] = 0; return 0;\n}\n",
			encoding="utf-8",
		)
		include = ["-I", str(header.parent.parent)]
	executable = app_dir / "srxy"
	defines = [
		f"-D{name}={json.dumps(str(tmp_path))}"
		for name in (
			"SRXY_HOME_PATH",
			"SRXY_PYTHONHOME",
			"SRXY_SITE_PACKAGES",
			"SRXY_PATH_PREFIX",
			"SRXY_TESSDATA",
			"SRXY_LOG_FILE",
		)
	]
	subprocess.run(  # noqa: S603
		[clang, *include, *defines, str(app_launcher_c_path()), "-o", str(executable)],
		check=True,
		capture_output=True,
	)
	caller = tmp_path / "caller café"
	caller.mkdir()
	args = ["--", "folder café # 100%/", "."] + [f"arg-{i}" for i in range(argument_count - 3)]
	# when
	result = subprocess.run([str(executable), *args], cwd=caller, check=False, capture_output=True)  # noqa: S603
	# then
	if argument_count == 60:
		assert result.returncode == 126
		assert not record.exists()
	else:
		assert result.returncode == 0, result.stderr
		values = record.read_bytes().decode("utf-8").split("\0")[:-1]
		assert values == [str(caller), "-m", "srxy", "--app-launch", *args]
