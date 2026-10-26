"""Launch intent and argument transport through generated installed entrypoints."""

from __future__ import annotations

import base64
import json
import os
import platform
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

from srxy.adapters.inbound.installer import install, launch_app


pytestmark = pytest.mark.unit


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux desktop entry")
def test_given_special_prefix_when_generating_desktop_entry_then_exec_is_quoted_and_marked(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	home = tmp_path / "home"
	monkeypatch.setattr(Path, "home", lambda: home)
	prefix = tmp_path / "srxy café # 100%"
	# when
	install._write_desktop_entry(prefix)
	text = (home / ".local/share/applications/srxy.desktop").read_text(encoding="utf-8")
	exec_line = next(line.removeprefix("Exec=") for line in text.splitlines() if line.startswith("Exec="))
	# then — desktop field codes require a doubled percent, even inside quotes.
	assert exec_line.startswith('/usr/bin/env "')
	assert "100%%" in exec_line
	assert shlex.split(exec_line.replace("%%", "%")) == ["/usr/bin/env", str(prefix / "bin/srxy"), "--app-launch"]


@pytest.mark.skipif(os.name == "nt", reason="Unix command shim")
def test_given_unix_command_shim_when_executed_then_preserves_cwd_and_unmarked_special_arguments(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setattr(install.platform, "system", lambda: "Linux")
	prefix = tmp_path / "srxy café # 100%"
	venv_bin = prefix / ".venv/bin"
	venv_bin.mkdir(parents=True)
	record = tmp_path / "record.json"
	probe = venv_bin / "srxy"
	probe.write_text(
		f"#!{sys.executable}\nimport json, os, sys\n"
		f"from pathlib import Path\nPath({str(record)!r}).write_text(json.dumps([os.getcwd(), sys.argv[1:]]))\n",
		encoding="utf-8",
	)
	probe.chmod(0o755)
	install.write_launcher(prefix)
	caller = tmp_path / "caller"
	caller.mkdir()
	args = ["--", "folder café # 100%/", "."]
	# when
	subprocess.run([str(prefix / "bin/srxy"), *args], cwd=caller, check=True)  # noqa: S603
	# then
	assert json.loads(record.read_text()) == [str(caller), args]


@pytest.mark.parametrize(
	("system", "relative", "marked"),
	[
		("Linux", "bin/srxy", True),
		("Darwin", "bin/srxy", True),
		("Windows", "bin/srxy.cmd", True),
		("Windows", "bin/srxy", True),
		("Windows", "bin/Srxy.exe", False),
	],
)
def test_given_installer_launch_route_when_spawning_then_app_intent_is_explicit(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	system: str,
	relative: str,
	marked: bool,
):
	# given
	prefix = tmp_path / "srxy café # 100%"
	launcher = prefix / relative
	launcher.parent.mkdir(parents=True)
	launcher.touch()
	seen: list[list[str]] = []

	def popen(cmd: list[str], **kwargs: object):
		seen.append(cmd)
		assert kwargs["start_new_session"] is True
		assert kwargs["stdin"] == subprocess.DEVNULL
		assert kwargs["stdout"] == subprocess.DEVNULL
		assert kwargs["stderr"] == subprocess.DEVNULL
		return object()

	monkeypatch.setattr(launch_app.platform, "system", lambda: system)
	monkeypatch.setattr(launch_app.subprocess, "Popen", popen)
	# when
	launch_app.launch_installed_app(prefix)
	# then
	assert seen == [[str(launcher.resolve()), *(["--app-launch"] if marked else [])]]


def test_given_windows_command_shim_when_generated_then_app_marker_is_absent(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setattr(install.platform, "system", lambda: "Windows")
	monkeypatch.setattr(install, "_write_windows_gui_exe", lambda _prefix: None)
	# when
	install.write_launcher(tmp_path)
	# then
	assert "--app-launch" not in (tmp_path / "bin/srxy.cmd").read_text(encoding="utf-8")


@pytest.mark.skipif(platform.system() != "Windows", reason="native Windows csc/ProcessStartInfo probe")
@pytest.mark.parametrize("pythonw", [True, False])
def test_given_windows_app_when_executed_then_marks_both_routes_and_preserves_cwd_and_argv(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	pythonw: bool,
):
	# given — compile a recorder instead of starting Qt.
	csc = install._find_csc()
	if csc is None:
		pytest.skip("csc.exe unavailable")
	prefix = tmp_path / "srxy café # 100%"
	scripts = prefix / ".venv/Scripts"
	scripts.mkdir(parents=True)
	record = tmp_path / "record.txt"
	monkeypatch.setenv("SRXY_STARTUP_PROBE", str(record))
	source = tmp_path / "Probe.cs"
	source.write_text(
		"using System; using System.IO; using System.Text; class Probe { "
		"static void Main(string[] args) { "
		"string[] lines = new string[args.Length + 1]; "
		"lines[0] = Convert.ToBase64String(Encoding.UTF8.GetBytes(Environment.CurrentDirectory)); "
		"for (int i = 0; i < args.Length; i++) "
		"lines[i + 1] = Convert.ToBase64String(Encoding.UTF8.GetBytes(args[i])); "
		'File.WriteAllLines(Environment.GetEnvironmentVariable("SRXY_STARTUP_PROBE"), lines); } }',
		encoding="utf-8",
	)
	probe = scripts / ("pythonw.exe" if pythonw else "srxy.exe")
	subprocess.run([str(csc), "/nologo", f"/out:{probe}", str(source)], check=True, capture_output=True)  # noqa: S603
	install.write_launcher(prefix)
	caller = tmp_path / "caller café"
	caller.mkdir()
	args = ["--", "folder café # 100%\\", "", 'quoted "folder"\\']
	# when
	subprocess.run([str(prefix / "bin/Srxy.exe"), *args], cwd=caller, check=True)  # noqa: S603
	deadline = time.monotonic() + 10
	while not record.exists() and time.monotonic() < deadline:
		time.sleep(0.02)
	# then
	assert record.exists(), "native child did not record its arguments"
	values = [base64.b64decode(line).decode("utf-8") for line in record.read_text(encoding="utf-8-sig").splitlines()]
	assert Path(values[0]) == caller
	assert values[1:] == [*(["-m", "srxy"] if pythonw else []), "--app-launch", *args]


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux Gio desktop launch")
@pytest.mark.parametrize("percent", [False, True])
def test_given_reserved_prefix_characters_when_desktop_entry_launches_then_path_remains_data(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	percent: bool,
):
	# given — use the desktop implementation's parser, rather than shell parsing.
	system_python = Path("/usr/bin/python3")
	if not system_python.is_file():
		pytest.skip("system Python unavailable for Gio probe")
	import_gio = subprocess.run(  # noqa: S603
		[str(system_python), "-c", "from gi.repository import Gio"],
		check=False,
		capture_output=True,
	)
	if import_gio.returncode:
		pytest.skip("system Gio bindings unavailable")
	home = tmp_path / "home"
	monkeypatch.setattr(Path, "home", lambda: home)
	prefix = tmp_path / ('srxy café # "quote" \\ $ `' + (" 100%" if percent else ""))
	launcher = prefix / "bin/srxy"
	launcher.parent.mkdir(parents=True)
	record = tmp_path / "desktop-argv.json"
	launcher.write_text(
		f"#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\n"
		f"Path({str(record)!r}).write_text(json.dumps(sys.argv[1:]))\n",
		encoding="utf-8",
	)
	launcher.chmod(0o755)
	install._write_desktop_entry(prefix)
	desktop = home / ".local/share/applications/srxy.desktop"
	# when
	result = subprocess.run(  # noqa: S603
		[
			str(system_python),
			"-c",
			"import sys; from gi.repository import Gio; "
			"app = Gio.DesktopAppInfo.new_from_filename(sys.argv[1]); "
			"assert app is not None; assert app.launch([], None)",
			str(desktop),
		],
		check=False,
		capture_output=True,
		text=True,
	)
	deadline = time.monotonic() + 5
	while not record.exists() and time.monotonic() < deadline:
		time.sleep(0.02)
	# then
	assert result.returncode == 0, result.stderr
	assert record.exists(), "desktop launch did not reach the executable at its literal path"
	assert json.loads(record.read_text()) == ["--app-launch"]
