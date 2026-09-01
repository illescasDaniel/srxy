"""Unit tests for the installer catalog probe's resilience to resolver failures.

The probe (``probe_catalog.py``) hits third-party APIs (GitHub releases, Homebrew,
martin-riedl) purely as an advisory health check for vendor download URLs — it is
not part of the code quality gate. A transient failure resolving one target (e.g.
BtbN's GitHub API returning a 5xx) must not crash the whole probe or hide results
for unrelated targets (Homebrew, UB-Mannheim, DanielMYT, ...).
"""

from __future__ import annotations

import time

import pytest

from srxy.adapters.inbound.installer import probe_catalog
from srxy.adapters.inbound.installer.resolve import ResolvedArtifact


pytestmark = pytest.mark.unit

_FAKE_FFMPEG = ResolvedArtifact(
	name="ffmpeg", version="1", url="https://example.invalid/ffmpeg.zip", sha256="", kind="zip"
)
_FAKE_TESSERACT = ResolvedArtifact(
	name="tesseract", version="1", url="https://example.invalid/tesseract.bin", sha256="", kind="binary"
)


def _boom(*_args: object, **_kwargs: object) -> ResolvedArtifact:
	raise RuntimeError("simulated transient 504")


def test_given_one_resolver_failing_when_probing_then_other_targets_still_probed_and_reported(
	monkeypatch: pytest.MonkeyPatch,
):
	# given — BtbN (ffmpeg linux/windows) is down; everything else (different hosts) is healthy.
	monkeypatch.setattr(probe_catalog, "_probe_catalog_maps", lambda: [])
	monkeypatch.setattr(probe_catalog, "resolve_ffmpeg_btbn", _boom)
	monkeypatch.setattr(probe_catalog, "resolve_ffmpeg_martin_riedl", lambda *, arch: _FAKE_FFMPEG)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_linux", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_windows", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_brew_bottles", lambda *, machine: (_FAKE_TESSERACT,))
	monkeypatch.setattr(probe_catalog, "probe_url", lambda url, headers=None: url)
	monkeypatch.setattr(probe_catalog, "_RESOLVE_RETRIES", 1)
	monkeypatch.setattr(time, "sleep", lambda _seconds: None)

	# when
	code = probe_catalog.main([])

	# then — overall failure reported (real signal something is down)...
	assert code == 1
	# ...but every target was still attempted independently (no crash-and-stop).
	targets = {label for label, _resolver, _headers in probe_catalog._resolver_targets()}
	assert targets == {
		"resolve:ffmpeg/linux",
		"resolve:ffmpeg/windows",
		"resolve:ffmpeg/darwin-arm64",
		"resolve:ffmpeg/darwin-amd64",
		"resolve:tesseract/linux",
		"resolve:tesseract/windows",
		"resolve:tesseract/darwin-arm64",
		"resolve:tesseract/darwin-x86_64",
	}


def test_given_all_resolvers_healthy_when_probing_then_succeeds(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr(probe_catalog, "_probe_catalog_maps", lambda: [])
	monkeypatch.setattr(probe_catalog, "resolve_ffmpeg_btbn", lambda *, system, machine: _FAKE_FFMPEG)
	monkeypatch.setattr(probe_catalog, "resolve_ffmpeg_martin_riedl", lambda *, arch: _FAKE_FFMPEG)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_linux", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_windows", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_brew_bottles", lambda *, machine: (_FAKE_TESSERACT,))
	monkeypatch.setattr(probe_catalog, "probe_url", lambda url, headers=None: url)

	# when
	code = probe_catalog.main([])

	# then
	assert code == 0


def test_given_resolver_transient_failure_then_succeeding_when_probing_then_retries_and_recovers(
	monkeypatch: pytest.MonkeyPatch,
):
	# given — fails once, then succeeds (simulates a transient blip within the retry budget).
	monkeypatch.setattr(probe_catalog, "_probe_catalog_maps", lambda: [])
	attempts = {"count": 0}

	def flaky_ffmpeg_btbn(*, system: str, machine: str) -> ResolvedArtifact:
		attempts["count"] += 1
		if attempts["count"] == 1:
			raise RuntimeError("simulated transient 504")
		return _FAKE_FFMPEG

	monkeypatch.setattr(probe_catalog, "resolve_ffmpeg_btbn", flaky_ffmpeg_btbn)
	monkeypatch.setattr(probe_catalog, "resolve_ffmpeg_martin_riedl", lambda *, arch: _FAKE_FFMPEG)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_linux", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_windows", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_brew_bottles", lambda *, machine: (_FAKE_TESSERACT,))
	monkeypatch.setattr(probe_catalog, "probe_url", lambda url, headers=None: url)
	monkeypatch.setattr(time, "sleep", lambda _seconds: None)

	# when
	code = probe_catalog.main([])

	# then — recovered within the retry budget, overall probe still succeeds.
	assert code == 0
	assert attempts["count"] >= 2


def test_given_resolver_raising_non_runtime_exception_when_probing_then_still_caught(
	monkeypatch: pytest.MonkeyPatch,
):
	"""A resolver could raise something other than RuntimeError (e.g. a stray
	KeyError from an unexpected API payload shape) — the probe must not crash."""
	# given
	monkeypatch.setattr(probe_catalog, "_probe_catalog_maps", lambda: [])
	monkeypatch.setattr(
		probe_catalog, "resolve_ffmpeg_btbn", lambda *, system, machine: (_ for _ in ()).throw(KeyError("bad payload"))
	)
	monkeypatch.setattr(probe_catalog, "resolve_ffmpeg_martin_riedl", lambda *, arch: _FAKE_FFMPEG)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_linux", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_windows", lambda: _FAKE_TESSERACT)
	monkeypatch.setattr(probe_catalog, "resolve_tesseract_brew_bottles", lambda *, machine: (_FAKE_TESSERACT,))
	monkeypatch.setattr(probe_catalog, "probe_url", lambda url, headers=None: url)
	monkeypatch.setattr(probe_catalog, "_RESOLVE_RETRIES", 1)
	monkeypatch.setattr(time, "sleep", lambda _seconds: None)

	# when
	code = probe_catalog.main([])

	# then — reported as a failure, not an uncaught traceback.
	assert code == 1
