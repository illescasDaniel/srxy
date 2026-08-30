"""Unit tests for installer download probing and vendor URL resolution."""

from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from srxy.adapters.inbound.installer import resolve as resolve_mod
from srxy.adapters.inbound.installer.download import probe_url
from srxy.adapters.inbound.installer.resolve import (
	resolve_ffmpeg_btbn,
	resolve_ffmpeg_martin_riedl,
	resolve_tesseract_brew_bottles,
	resolve_tesseract_linux,
	resolve_tesseract_windows,
)


pytestmark = pytest.mark.unit


class _FakeResponse(io.BytesIO):
	def __init__(self, payload: bytes, *, url: str = "https://example.invalid/x", status: int = 206):
		super().__init__(payload)
		self.headers: dict[str, str] = {"Content-Length": str(len(payload))}
		self._url = url
		self.status = status

	def geturl(self) -> str:
		return self._url

	def getcode(self) -> int:
		return self.status


def test_given_https_url_when_probing_then_returns_final_url(monkeypatch: pytest.MonkeyPatch):
	final = "https://cdn.example.invalid/artifact.bin"

	def fake_urlopen(request: urllib.request.Request, timeout: float = 0.0) -> _FakeResponse:
		assert request.full_url.startswith("https://")
		assert request.get_header("Range") == "bytes=0-0"
		assert timeout > 0
		return _FakeResponse(b"P", url=final, status=206)

	monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
	assert probe_url("https://example.invalid/artifact.bin") == final


def test_given_http_url_when_probing_then_rejects(monkeypatch: pytest.MonkeyPatch):
	def fail_urlopen(*_a: object, **_k: object) -> _FakeResponse:
		raise AssertionError("must not connect")

	monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
	with pytest.raises(RuntimeError, match="non-https"):
		probe_url("http://example.invalid/x")


def test_given_transient_urlerror_when_fetching_json_then_retries(monkeypatch: pytest.MonkeyPatch):
	calls = {"n": 0}
	payload = [{"tag_name": "ok", "draft": False, "assets": []}]

	def flaky_urlopen(_request: urllib.request.Request, timeout: float = 0.0) -> _FakeResponse:
		_ = timeout
		calls["n"] += 1
		if calls["n"] < 3:
			raise urllib.error.URLError(ConnectionResetError(104, "Connection reset by peer"))
		return _FakeResponse(b'[{"tag_name":"ok","draft":false,"assets":[]}]', url=_request.full_url)

	monkeypatch.setattr(urllib.request, "urlopen", flaky_urlopen)
	monkeypatch.setattr(resolve_mod.time, "sleep", lambda _s: None)
	assert resolve_mod._http_json("https://example.invalid/api.json") == payload  # pyright: ignore[reportPrivateUsage]
	assert calls["n"] == 3


def test_given_transient_urlerror_when_probing_then_retries(monkeypatch: pytest.MonkeyPatch):
	calls = {"n": 0}
	final = "https://cdn.example.invalid/ok.bin"

	def flaky_urlopen(_request: urllib.request.Request, timeout: float = 0.0) -> _FakeResponse:
		_ = timeout
		calls["n"] += 1
		if calls["n"] < 2:
			raise urllib.error.URLError(ConnectionResetError(104, "Connection reset by peer"))
		return _FakeResponse(b"P", url=final, status=206)

	monkeypatch.setattr(urllib.request, "urlopen", flaky_urlopen)
	monkeypatch.setattr("srxy.adapters.inbound.installer.download.time.sleep", lambda _s: None)
	assert probe_url("https://example.invalid/artifact.bin") == final
	assert calls["n"] == 2


def test_given_btbn_releases_when_resolving_linux_then_picks_lgpl_shared(monkeypatch: pytest.MonkeyPatch):
	payload = [
		{
			"tag_name": "latest",
			"draft": False,
			"assets": [
				{
					"name": "ffmpeg-n8.1-latest-linux64-lgpl-shared-8.1.tar.xz",
					"browser_download_url": "https://example.invalid/latest.tar.xz",
				}
			],
		},
		{
			"tag_name": "autobuild-2026-08-30-13-12",
			"draft": False,
			"assets": [
				{
					"name": "ffmpeg-N-126335-gb32f8d1c23-linux64-lgpl-shared.tar.xz",
					"browser_download_url": "https://example.invalid/master.tar.xz",
				},
				{
					"name": "ffmpeg-n8.1.2-50-g1a748fe2cd-linux64-lgpl-shared-8.1.tar.xz",
					"browser_download_url": "https://example.invalid/release.tar.xz",
				},
			],
		},
	]

	def fake_json(url: str) -> object:
		assert "BtbN/FFmpeg-Builds" in url
		return payload

	monkeypatch.setattr(resolve_mod, "_http_json", fake_json)
	resolved = resolve_ffmpeg_btbn(system="linux", machine="x86_64")
	assert resolved.url == "https://example.invalid/release.tar.xz"
	assert resolved.kind == "archive"
	assert "n8.1.2" in resolved.version


def test_given_martin_riedl_redirect_when_resolving_then_uses_final_snapshot(
	monkeypatch: pytest.MonkeyPatch,
):
	final = "https://ffmpeg.martin-riedl.de/download/macos/arm64/1787073674_9.0.1/ffmpeg.zip"

	def fake_follow(url: str) -> str:
		assert "redirect/latest/macos/arm64/release" in url
		return final

	monkeypatch.setattr(resolve_mod, "_follow_redirect_url", fake_follow)
	resolved = resolve_ffmpeg_martin_riedl(arch="arm64")
	assert resolved.url == final
	assert resolved.version == "9.0.1"
	assert resolved.kind == "zip"


def test_given_tesseract_static_releases_when_resolving_then_picks_x86_64(
	monkeypatch: pytest.MonkeyPatch,
):
	payload = [
		{
			"tag_name": "tesseract-5.5.3",
			"draft": False,
			"assets": [
				{
					"name": "tesseract.x86_64",
					"browser_download_url": "https://example.invalid/tesseract.x86_64",
				}
			],
		}
	]
	monkeypatch.setattr(resolve_mod, "_http_json", lambda _url: payload)
	resolved = resolve_tesseract_linux()
	assert resolved.url.endswith("tesseract.x86_64")
	assert resolved.version == "5.5.3"
	assert resolved.kind == "binary"


def test_given_ub_mannheim_releases_when_resolving_then_picks_w64_setup(
	monkeypatch: pytest.MonkeyPatch,
):
	payload = [
		{
			"tag_name": "v5.4.0.20240606",
			"draft": False,
			"prerelease": False,
			"assets": [
				{
					"name": "tesseract-ocr-w64-setup-5.4.0.20240606.exe",
					"browser_download_url": "https://example.invalid/setup.exe",
				}
			],
		}
	]
	monkeypatch.setattr(resolve_mod, "_http_json", lambda _url: payload)
	resolved = resolve_tesseract_windows()
	assert resolved.url.endswith("setup.exe")
	assert resolved.kind == "nsis_installer"


def test_given_brew_formula_api_when_resolving_arm64_then_uses_sonoma_digest(
	monkeypatch: pytest.MonkeyPatch,
):
	def fake_json(url: str) -> object:
		formula = url.rsplit("/", 1)[-1].removesuffix(".json")
		return {
			"versions": {"stable": "1.2.3"},
			"bottle": {
				"stable": {
					"files": {
						"arm64_sonoma": {"sha256": "a" * 64},
						"sonoma": {"sha256": "b" * 64},
					}
				}
			},
			"name": formula,
		}

	monkeypatch.setattr(resolve_mod, "_http_json", fake_json)
	bottles = resolve_tesseract_brew_bottles(machine="arm64")
	assert bottles
	assert bottles[0].formula == "tesseract"
	assert bottles[0].sha256 == "a" * 64
	assert bottles[0].url.endswith(bottles[0].sha256)


def test_given_brew_formula_api_when_resolving_intel_then_uses_sonoma_digest(
	monkeypatch: pytest.MonkeyPatch,
):
	def fake_json(url: str) -> object:
		return {
			"versions": {"stable": "9.9.9"},
			"bottle": {"stable": {"files": {"sonoma": {"sha256": "c" * 64}}}},
		}

	monkeypatch.setattr(resolve_mod, "_http_json", fake_json)
	bottles = resolve_tesseract_brew_bottles(machine="x86_64")
	assert bottles[0].sha256 == "c" * 64
	assert bottles[0].version == "9.9.9"
