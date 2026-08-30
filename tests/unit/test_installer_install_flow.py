"""Wire-through install flow tests (mocked uv / vendor; no network)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from srxy.adapters.inbound.installer import install as install_mod
from srxy.adapters.inbound.installer.install import InstallOptions, install_srxy
from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION
from srxy.i18n import set_language, tr


pytestmark = pytest.mark.unit


def _stub_windows_install(monkeypatch: pytest.MonkeyPatch, *, captured_cmds: list[list[str]]):
	monkeypatch.setattr(install_mod, "_is_windows", lambda: True)
	monkeypatch.setattr(install_mod, "_is_linux", lambda: False)
	# Keep default stubs free of host GPU: dedicated tests cover the CUDA step.
	monkeypatch.setattr(install_mod, "should_ensure_windows_cuda_torch", lambda **_k: False)

	def fake_run(cmd: list[str], env: dict[str, str] | None = None):
		_ = env
		captured_cmds.append(list(cmd))

	def fake_install_uv(prefix: Path, progress: object | None = None):
		_ = progress
		uv = prefix / "vendor" / "uv" / "uv.exe"
		uv.parent.mkdir(parents=True, exist_ok=True)
		uv.write_bytes(b"uv")
		return uv

	def fake_subprocess_run(cmd: list[str], **kwargs: object):
		_ = cmd, kwargs
		return SimpleNamespace(returncode=0, stdout="", stderr="")

	monkeypatch.setattr(install_mod, "_run", fake_run)
	monkeypatch.setattr(install_mod, "install_uv", fake_install_uv)
	monkeypatch.setattr(install_mod.subprocess, "run", fake_subprocess_run)
	monkeypatch.setattr(install_mod, "write_launcher", lambda _prefix: None)
	monkeypatch.setattr(install_mod, "_package_version", lambda _venv=None: "1.6.4")


def test_given_windows_semantic_and_nvidia_when_install_srxy_then_ensures_cuda_torch(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	from collections.abc import Callable

	from srxy.adapters.inbound.installer.cuda_torch import cuda_wheel_index_url

	captured: list[list[str]] = []
	_stub_windows_install(monkeypatch, captured_cmds=captured)
	monkeypatch.setattr(install_mod, "should_ensure_windows_cuda_torch", lambda **_k: True)

	def fake_ensure(
		*,
		uv: Path,
		python: Path,
		env: dict[str, str],
		run: Callable[..., None],
		**_kwargs: object,
	):
		_ = python
		run(
			[
				str(uv),
				"pip",
				"install",
				"--reinstall-package",
				"torch",
				"torchvision",
				"torchaudio",
				"--index-url",
				cuda_wheel_index_url("cu130"),
			],
			env=env,
		)
		return "installed"

	monkeypatch.setattr(install_mod, "ensure_windows_cuda_torch", fake_ensure)
	set_language("en")

	prefix = tmp_path / "Programs" / "srxy"
	options = InstallOptions(
		prefix=prefix,
		download_tesseract=False,
		download_ffmpeg=False,
		install_semantic=True,
		add_to_path=False,
		srxy_spec="srxy==1.6.4",
		confirm_unsafe=True,
	)

	statuses: list[str] = []
	manifest = install_srxy(options, status=statuses.append)

	pip_cmds = [cmd for cmd in captured if len(cmd) >= 3 and cmd[1:3] == ["pip", "install"]]
	assert pip_cmds[0][3] == "srxy[semantic]==1.6.4"
	cuda_cmds = [cmd for cmd in pip_cmds if "--index-url" in cmd]
	assert len(cuda_cmds) == 1
	assert cuda_cmds[0][cuda_cmds[0].index("--index-url") + 1] == cuda_wheel_index_url("cu130")
	assert any("CUDA PyTorch" in message for message in statuses)
	assert manifest.semantic is True


def test_given_windows_semantic_nvidia_when_planning_phases_then_includes_cuda_torch(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	from srxy.adapters.inbound.installer.install import plan_install_phases

	monkeypatch.setattr(install_mod, "_is_windows", lambda: True)
	monkeypatch.setattr(install_mod, "should_ensure_windows_cuda_torch", lambda **_k: True)
	set_language("en")
	options = InstallOptions(
		prefix=tmp_path / "srxy",
		download_tesseract=False,
		download_ffmpeg=False,
		install_semantic=True,
		add_to_path=False,
	)
	keys = [phase.key for phase in plan_install_phases(options)]
	assert keys == ["uv", "venv", "package", "cuda_torch", "launcher"]


def test_given_windows_host_when_install_srxy_without_semantic_then_pip_uses_bare_spec(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	captured: list[list[str]] = []
	_stub_windows_install(monkeypatch, captured_cmds=captured)
	set_language("en")

	prefix = tmp_path / "Programs" / "srxy"
	options = InstallOptions(
		prefix=prefix,
		download_tesseract=False,
		download_ffmpeg=False,
		install_semantic=False,
		add_to_path=False,
		srxy_spec="srxy==1.6.4",
		confirm_unsafe=True,
	)

	# when
	manifest = install_srxy(options)

	# then — pywin32 is core; no [windows] extra
	pip_cmds = [cmd for cmd in captured if len(cmd) >= 4 and cmd[1:3] == ["pip", "install"]]
	assert pip_cmds, f"no pip install in {captured!r}"
	assert pip_cmds[0][3] == "srxy==1.6.4"
	assert manifest.extra["srxy_spec"] == "srxy==1.6.4"
	assert manifest.privacy_ack_version == PRIVACY_NOTICE_VERSION


def test_given_windows_semantic_when_install_srxy_then_pip_uses_semantic_extra(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	captured: list[list[str]] = []
	_stub_windows_install(monkeypatch, captured_cmds=captured)
	set_language("en")

	prefix = tmp_path / "Programs" / "srxy"
	options = InstallOptions(
		prefix=prefix,
		download_tesseract=False,
		download_ffmpeg=False,
		install_semantic=True,
		add_to_path=False,
		srxy_spec="srxy==1.6.4",
		confirm_unsafe=True,
	)

	# when
	manifest = install_srxy(options)

	# then
	pip_cmds = [cmd for cmd in captured if len(cmd) >= 4 and cmd[1:3] == ["pip", "install"]]
	assert pip_cmds[0][3] == "srxy[semantic]==1.6.4"
	assert manifest.extra["srxy_spec"] == "srxy[semantic]==1.6.4"
	assert manifest.semantic is True


def test_given_spanish_language_when_install_srxy_then_status_has_no_unicode_ellipsis(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	captured: list[list[str]] = []
	_stub_windows_install(monkeypatch, captured_cmds=captured)
	set_language("es")
	statuses: list[str] = []

	prefix = tmp_path / "Programs" / "srxy"
	options = InstallOptions(
		prefix=prefix,
		download_tesseract=False,
		download_ffmpeg=False,
		install_semantic=False,
		add_to_path=False,
		srxy_spec="srxy==1.6.4",
		confirm_unsafe=True,
	)

	install_srxy(options, status=statuses.append)

	assert any("Instalando uv" in message for message in statuses)
	assert any("\u2026" in message for message in statuses), "catalog still uses ellipsis"
	# Protocol sanitization happens in __main__._emit, not install_srxy itself.
	assert tr("installer.status.installing_uv").endswith("\u2026")


def test_given_unix_host_when_install_srxy_then_omits_windows_extra(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	captured: list[list[str]] = []
	monkeypatch.setattr(install_mod, "_is_windows", lambda: False)
	monkeypatch.setattr(install_mod, "_is_linux", lambda: True)

	def fake_run(cmd: list[str], env: dict[str, str] | None = None):
		_ = env
		captured.append(list(cmd))

	def fake_install_uv(prefix: Path, progress: object | None = None):
		_ = progress
		uv = prefix / "vendor" / "uv" / "uv"
		uv.parent.mkdir(parents=True, exist_ok=True)
		uv.write_bytes(b"uv")
		return uv

	monkeypatch.setattr(install_mod, "_run", fake_run)
	monkeypatch.setattr(install_mod, "install_uv", fake_install_uv)
	monkeypatch.setattr(
		install_mod.subprocess,
		"run",
		lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="", stderr=""),
	)
	monkeypatch.setattr(install_mod, "write_launcher", lambda _prefix: None)
	monkeypatch.setattr(install_mod, "_install_icons", lambda _prefix: (None, []))
	monkeypatch.setattr(install_mod, "_write_desktop_entry", lambda _prefix: None)
	monkeypatch.setattr(install_mod, "_package_version", lambda _venv=None: "1.6.4")
	set_language("en")

	prefix = tmp_path / "opt" / "srxy"
	options = InstallOptions(
		prefix=prefix,
		download_tesseract=False,
		download_ffmpeg=False,
		install_semantic=True,
		add_to_path=False,
		srxy_spec="srxy==1.6.4",
		confirm_unsafe=True,
	)

	manifest = install_srxy(options)
	pip_cmds = [cmd for cmd in captured if len(cmd) >= 4 and cmd[1:3] == ["pip", "install"]]
	assert pip_cmds[0][3] == "srxy[semantic]==1.6.4"
	assert manifest.extra["srxy_spec"] == "srxy[semantic]==1.6.4"
