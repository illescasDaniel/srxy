"""Unit tests for the one-click online installer (not the PySide offline wizard)."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from srxy.adapters.inbound.installer.catalog import vendor_downloads_supported
from srxy.adapters.inbound.installer.install import InstallOptions
from srxy.adapters.inbound.installer_online.__main__ import main
from srxy.adapters.inbound.installer_online.options import build_online_install_options
from srxy.adapters.inbound.installer_online.server import (
	TOKEN_HEADER,
	InstallSession,
	create_online_installer_server,
	start_client_watchdog,
)


pytestmark = [pytest.mark.unit, pytest.mark.xdist_group("installer_online")]


def test_given_help_flag_when_running_online_main_then_exits_zero_without_server(
	capsys: pytest.CaptureFixture[str],
):
	# given / when
	with pytest.raises(SystemExit) as exc:
		main(["--help"])

	# then
	assert exc.value.code == 0
	assert "online" in capsys.readouterr().out.lower()


def test_given_version_flag_when_running_online_main_then_prints_version(
	capsys: pytest.CaptureFixture[str],
):
	# given / when
	code = main(["--version"])

	# then
	assert code == 0
	assert capsys.readouterr().out.strip()


def test_given_gpu_when_building_online_options_then_semantic_on_prefetch_off(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_GPU", "1")
	monkeypatch.delenv("SRXY_INSTALLER_FORCE_NO_GPU", raising=False)
	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==9.9.9")

	# when
	options = build_online_install_options(prefix=tmp_path / "srxy")

	# then
	assert options.install_semantic is True
	assert options.prefetch_models is False
	assert options.add_to_path is True
	assert options.download_tesseract is vendor_downloads_supported()
	assert options.download_ffmpeg is vendor_downloads_supported()
	assert options.srxy_spec == "srxy==9.9.9"
	assert options.prefix == (tmp_path / "srxy").resolve()


def test_given_no_gpu_when_building_online_options_then_semantic_off(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	monkeypatch.delenv("SRXY_INSTALLER_FORCE_GPU", raising=False)
	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==1.6.0")

	# when
	options = build_online_install_options(prefix=tmp_path / "app")

	# then
	assert options.install_semantic is False
	assert options.prefetch_models is False


def test_given_darwin_arm64_when_building_online_options_then_vendor_downloads_on(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer import catalog as catalog_mod
	from srxy.adapters.inbound.installer_online import options as options_mod

	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "arm64")
	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==1.6.0")

	# when
	options = options_mod.build_online_install_options(prefix=tmp_path / "app")

	# then
	assert options.download_tesseract is True
	assert options.download_ffmpeg is True


def test_given_windows_when_building_online_options_then_vendor_downloads_off(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer import catalog as catalog_mod
	from srxy.adapters.inbound.installer_online import options as options_mod

	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Windows")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "AMD64")
	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==1.6.0")

	# when
	options = options_mod.build_online_install_options(prefix=tmp_path / "app")

	# then
	assert options.download_tesseract is False
	assert options.download_ffmpeg is False


def test_given_mocked_pypi_when_resolving_pypi_spec_then_pins_compatible_version(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.adapters.inbound.installer import package_spec

	monkeypatch.delenv("SRXY_INSTALL_SPEC", raising=False)

	def fake_fetch(*, timeout: float = 15.0) -> dict[str, Any]:
		_ = timeout
		return {
			"info": {
				"version": "1.6.3",
				"requires_dist": ["PySide6>=6.6", "cryptography>=44"],
			}
		}

	monkeypatch.setattr(package_spec, "fetch_pypi_srxy_info", fake_fetch)

	# when
	spec = package_spec.resolve_pypi_install_spec()

	# then
	assert spec == "srxy==1.6.3"


def test_given_pypi_without_pyside_when_resolving_pypi_spec_then_raises(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.adapters.inbound.installer import package_spec

	monkeypatch.delenv("SRXY_INSTALL_SPEC", raising=False)

	def fake_fetch(*, timeout: float = 15.0) -> dict[str, Any]:
		_ = timeout
		return {"info": {"version": "1.6.3", "requires_dist": ["cryptography>=44"]}}

	monkeypatch.setattr(package_spec, "fetch_pypi_srxy_info", fake_fetch)

	# when / then
	with pytest.raises(RuntimeError, match="PySide6"):
		package_spec.resolve_pypi_install_spec()


def test_given_fresh_interpreter_when_importing_installer_install_then_does_not_load_pyside():
	# given / when — online AppImage imports install without PySide6 in the wizard venv
	import subprocess
	import sys

	probe = (
		"from srxy.adapters.inbound.installer.install import InstallOptions, install_srxy; "
		"import sys; "
		"assert 'PySide6' not in sys.modules; "
		"assert 'srxy.adapters.inbound.installer.app' not in sys.modules"
	)
	result = subprocess.run(  # noqa: S603
		[sys.executable, "-c", probe],
		check=False,
		capture_output=True,
		text=True,
	)

	# then
	assert result.returncode == 0, result.stderr


class _ServerHarness:
	def __init__(self):
		self.url = ""
		self.session: InstallSession | None = None
		self.server: ThreadingHTTPServer | None = None
		self._serve_thread: threading.Thread | None = None

	def start(
		self,
		*,
		client_watchdog: bool = False,
		client_idle_seconds: float = 3.0,
		client_grace_seconds: float = 20.0,
		url_file: Path | None = None,
	):
		# Bind on the test thread — macOS/xdist was flaky when bind ran inside a daemon.
		url, session, server = create_online_installer_server()
		self.url = url
		self.session = session
		self.server = server
		self._serve_thread = threading.Thread(target=server.serve_forever, daemon=True)
		self._serve_thread.start()
		if client_watchdog:
			start_client_watchdog(
				session,
				idle_seconds=client_idle_seconds,
				grace_seconds=client_grace_seconds,
			)
		if url_file is not None:
			url_file.parent.mkdir(parents=True, exist_ok=True)
			url_file.write_text(url + "\n", encoding="utf-8")

	def stop(self):
		if self.session is not None:
			self.session.stop_event.set()
		if self.server is not None:
			self.server.shutdown()
			self.server.server_close()
		if self._serve_thread is not None:
			self._serve_thread.join(timeout=5)

	@property
	def token(self) -> str:
		assert self.session is not None
		return self.session.token

	def api(self, path: str, *, token: str | None = None, data: dict[str, Any] | None = None) -> tuple[int, Any]:
		parsed = urlparse(self.url)
		use_token = self.token if token is None else token
		sep = "&" if "?" in path else "?"
		full = f"{parsed.scheme}://{parsed.netloc}{path}{sep}t={use_token}"
		body = None
		headers = {TOKEN_HEADER: use_token}
		method = "GET"
		if data is not None:
			method = "POST"
			body = json.dumps(data).encode("utf-8")
			headers["Content-Type"] = "application/json"
		req = urllib.request.Request(full, data=body, headers=headers, method=method)  # noqa: S310
		try:
			with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
				raw = resp.read().decode("utf-8")
				payload: Any = json.loads(raw) if raw and path.startswith("/api/") else raw
				return resp.status, payload
		except urllib.error.HTTPError as exc:
			raw = exc.read().decode("utf-8")
			try:
				payload = json.loads(raw) if raw else {}
			except json.JSONDecodeError:
				payload = {"error": raw}
			return exc.code, payload


@pytest.fixture
def online_server(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_LANGUAGE", "en")
	harness = _ServerHarness()
	harness.start(client_watchdog=False)
	try:
		yield harness
	finally:
		harness.stop()


def test_given_created_server_when_started_then_uses_daemon_request_threads(
	online_server: _ServerHarness,
):
	# then — required so xdist workers can exit after HTTP tests
	assert online_server.server is not None
	assert online_server.server.daemon_threads is True


def test_given_missing_token_when_calling_api_then_rejects(online_server: _ServerHarness):
	# when
	bad_token = "wrong-token"  # noqa: S105
	code, payload = online_server.api("/api/status", token=bad_token)

	# then
	assert code == 401
	assert "token" in str(payload.get("error", "")).lower()


def test_given_valid_token_when_bootstrapping_then_returns_privacy_text(online_server: _ServerHarness):
	# when
	code, payload = online_server.api("/api/bootstrap")

	# then
	assert code == 200
	assert isinstance(payload, dict)
	assert payload.get("privacy_text")
	assert payload.get("prefix")
	assert payload["strings"]["install"]
	assert payload["strings"]["uninstall"]
	assert payload["strings"]["launch"]
	assert payload["strings"]["confirm_uninstall"]


def test_given_install_without_ack_when_posting_then_returns_400(
	online_server: _ServerHarness,
	tmp_path: Path,
):
	# when
	code, payload = online_server.api(
		"/api/install",
		data={"privacy_ack": False, "prefix": str(tmp_path / "srxy")},
	)

	# then
	assert code == 400
	assert "privacy" in str(payload.get("error", "")).lower()


def test_given_mocked_install_when_posting_install_then_status_becomes_done(
	online_server: _ServerHarness,
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer_online import server as server_mod

	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==1.6.0")

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int, int, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
	):
		_ = options
		if status:
			status("fake install")
		if task:
			task(1, 1, "done step")
		if progress:
			progress(1, 1, "bytes")

	monkeypatch.setattr(server_mod, "install_srxy", fake_install)

	# when
	code, _ = online_server.api(
		"/api/install",
		data={"privacy_ack": True, "prefix": str(tmp_path / "prefix")},
	)
	assert code == 200

	deadline = time.monotonic() + 5
	snap: dict[str, Any] = {}
	while time.monotonic() < deadline:
		status_code, snap = online_server.api("/api/status")
		assert status_code == 200
		assert isinstance(snap, dict)
		if snap.get("status") in {"done", "error"}:
			break
		time.sleep(0.05)

	# then
	assert snap.get("status") == "done", snap
	assert snap.get("overall") == 1.0
	assert snap.get("can_launch") is True


def test_given_successful_install_when_posting_launch_then_starts_app_and_stops(
	online_server: _ServerHarness,
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer_online import server as server_mod

	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==1.6.0")
	launched: list[str] = []

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int, int, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
	):
		_ = status, progress, task
		prefix = Path(options.prefix)
		bin_dir = prefix / "bin"
		bin_dir.mkdir(parents=True)
		(bin_dir / "srxy").write_text("#!/bin/sh\n", encoding="utf-8")

	def fake_launch(prefix: Path | str):
		launched.append(str(Path(prefix).resolve()))

	monkeypatch.setattr(server_mod, "install_srxy", fake_install)
	monkeypatch.setattr(server_mod, "launch_installed_app", fake_launch)

	prefix = tmp_path / "prefix"
	code, _ = online_server.api(
		"/api/install",
		data={"privacy_ack": True, "prefix": str(prefix)},
	)
	assert code == 200

	deadline = time.monotonic() + 5
	snap: dict[str, Any] = {}
	while time.monotonic() < deadline:
		status_code, snap = online_server.api("/api/status")
		assert status_code == 200
		assert isinstance(snap, dict)
		if snap.get("status") in {"done", "error"}:
			break
		time.sleep(0.05)
	assert snap.get("status") == "done"
	assert snap.get("can_launch") is True

	# when
	launch_code, launch_payload = online_server.api("/api/launch", data={})

	# then
	assert launch_code == 200
	assert launch_payload.get("ok") is True
	assert launched == [str(prefix.resolve())]
	assert online_server.session is not None
	assert online_server.session.stop_event.is_set()


def test_given_mocked_uninstall_when_posting_uninstall_then_status_becomes_done(
	online_server: _ServerHarness,
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer_online import server as server_mod

	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)
	(prefix / ".venv").mkdir()

	def fake_uninstall(
		target: Path,
		*,
		status: Callable[[str], None] | None = None,
		confirm_unsafe: bool = False,
	):
		_ = confirm_unsafe
		assert target == prefix.resolve()
		if status:
			status("fake uninstall")
		# Simulate shared uninstall removing the tree.
		import shutil

		shutil.rmtree(target)

	monkeypatch.setattr(server_mod, "uninstall_prefix", fake_uninstall)

	# when
	code, _ = online_server.api(
		"/api/uninstall",
		data={"prefix": str(prefix)},
	)
	assert code == 200

	deadline = time.monotonic() + 5
	snap: dict[str, Any] = {}
	while time.monotonic() < deadline:
		status_code, snap = online_server.api("/api/status")
		assert status_code == 200
		assert isinstance(snap, dict)
		if snap.get("status") in {"done", "error"}:
			break
		time.sleep(0.05)

	# then
	assert snap.get("status") == "done", snap
	assert not prefix.exists()
	assert snap.get("can_launch") is False


def test_given_uninstall_error_when_posting_install_then_starts_successfully(
	online_server: _ServerHarness,
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given — failed uninstall must not permanently lock the session
	from srxy.adapters.inbound.installer_online import server as server_mod

	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==1.6.0")
	prefix = tmp_path / "Applications" / "srxy"
	prefix.mkdir(parents=True)

	def fake_uninstall(
		target: Path,
		*,
		status: Callable[[str], None] | None = None,
		confirm_unsafe: bool = False,
	):
		_ = target, status, confirm_unsafe
		raise RuntimeError("uninstall boom")

	def fake_install(
		options: InstallOptions,
		*,
		status: Callable[[str], None] | None = None,
		progress: Callable[[int, int, str], None] | None = None,
		task: Callable[[int, int, str], None] | None = None,
	):
		_ = options, progress, task
		if status:
			status("fake install after error")

	monkeypatch.setattr(server_mod, "uninstall_prefix", fake_uninstall)
	monkeypatch.setattr(server_mod, "install_srxy", fake_install)

	code, _ = online_server.api(
		"/api/uninstall",
		data={"prefix": str(prefix)},
	)
	assert code == 200

	deadline = time.monotonic() + 5
	snap: dict[str, Any] = {}
	while time.monotonic() < deadline:
		status_code, snap = online_server.api("/api/status")
		assert status_code == 200
		assert isinstance(snap, dict)
		if snap.get("status") in {"done", "error"}:
			break
		time.sleep(0.05)
	assert snap.get("status") == "error", snap

	# when — retry with Install
	install_code, _ = online_server.api(
		"/api/install",
		data={"privacy_ack": True, "prefix": str(tmp_path / "fresh")},
	)

	# then
	assert install_code == 200
	deadline = time.monotonic() + 5
	while time.monotonic() < deadline:
		status_code, snap = online_server.api("/api/status")
		assert status_code == 200
		assert isinstance(snap, dict)
		if snap.get("status") in {"done", "error"}:
			break
		time.sleep(0.05)
	assert snap.get("status") == "done", snap
	assert snap.get("can_launch") is True


def test_given_no_client_when_grace_expires_then_server_stops(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_LANGUAGE", "en")
	harness = _ServerHarness()
	harness.start(client_watchdog=True, client_grace_seconds=0.3, client_idle_seconds=0.3)
	assert harness.session is not None

	# when — no authenticated client requests
	stopped = harness.session.stop_event.wait(timeout=3)

	# then
	assert stopped
	harness.stop()


def test_given_client_heartbeat_stops_when_idle_expires_then_server_stops(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_LANGUAGE", "en")
	harness = _ServerHarness()
	harness.start(client_watchdog=True, client_grace_seconds=5.0, client_idle_seconds=0.4)

	# when — one heartbeat, then silence
	code, _ = harness.api("/api/status")
	assert code == 200
	assert harness.session is not None
	stopped = harness.session.stop_event.wait(timeout=3)

	# then
	assert stopped
	harness.stop()


def test_given_url_file_when_starting_with_no_browser_then_writes_url(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	monkeypatch.setenv("SRXY_LANGUAGE", "en")
	url_path = tmp_path / "installer.url"
	harness = _ServerHarness()
	harness.start(client_watchdog=False, url_file=url_path)

	# when / then
	assert url_path.is_file()
	written = url_path.read_text(encoding="utf-8").strip()
	assert written == harness.url
	assert written.startswith("http://127.0.0.1:")
	harness.stop()


def test_given_shutdown_post_when_empty_body_then_accepts(online_server: _ServerHarness):
	# when — sendBeacon-style empty / "{}" body
	code, payload = online_server.api("/api/shutdown", data={})

	# then
	assert code == 200
	assert payload.get("ok") is True
	assert online_server.session is not None
	assert online_server.session.stop_event.is_set()
