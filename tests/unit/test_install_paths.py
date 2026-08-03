from __future__ import annotations

from pathlib import Path

import pytest

from srxy.application.install_paths import (
	default_cache_root,
	default_install_prefix,
	models_root,
	resolve_ffmpeg_binary,
	resolve_tesseract_binary,
	srxy_home,
)


pytestmark = pytest.mark.unit


def test_given_no_srxy_home_when_resolving_cache_then_uses_dot_cache(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_HOME", raising=False)
	monkeypatch.delenv("SRXY_CACHE_DIR", raising=False)

	# when / then
	assert srxy_home() is None
	assert default_cache_root() == Path.home() / ".cache" / "srxy"
	assert models_root() == default_cache_root()


def test_given_srxy_home_when_resolving_paths_then_uses_prefix(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_HOME", str(tmp_path))
	monkeypatch.delenv("SRXY_CACHE_DIR", raising=False)
	(tmp_path / "vendor" / "tesseract" / "bin").mkdir(parents=True)
	(tmp_path / "vendor" / "ffmpeg" / "bin").mkdir(parents=True)
	tess = tmp_path / "vendor" / "tesseract" / "bin" / "tesseract"
	ffmpeg = tmp_path / "vendor" / "ffmpeg" / "bin" / "ffmpeg"
	tess.write_text("", encoding="utf-8")
	ffmpeg.write_text("", encoding="utf-8")

	# when / then
	assert srxy_home() == tmp_path.resolve()
	assert default_cache_root() == tmp_path.resolve() / "cache"
	assert models_root() == tmp_path.resolve() / "models"
	assert resolve_tesseract_binary() == tess
	assert resolve_ffmpeg_binary() == ffmpeg


def test_given_cache_dir_override_when_resolving_cache_then_prefers_override(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	override = tmp_path / "custom-cache"
	monkeypatch.setenv("SRXY_CACHE_DIR", str(override))
	monkeypatch.setenv("SRXY_HOME", str(tmp_path / "home"))

	# when / then
	assert default_cache_root() == override


def test_given_home_when_default_install_prefix_then_uses_applications():
	# given / when / then
	assert default_install_prefix() == Path.home() / "Applications" / "srxy"
