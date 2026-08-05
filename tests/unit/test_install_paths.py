from __future__ import annotations

from pathlib import Path

import pytest

from srxy.application.install_paths import (
	default_cache_root,
	models_root,
	resolve_ffmpeg_binary,
	resolve_tesseract_binary,
	srxy_home,
)


pytestmark = pytest.mark.unit


def test_given_no_srxy_home_when_resolving_cache_then_uses_os_default(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	import platform

	monkeypatch.delenv("SRXY_HOME", raising=False)
	monkeypatch.delenv("SRXY_CACHE_DIR", raising=False)

	# when / then
	assert srxy_home() is None
	if platform.system().lower() == "windows":
		local = Path.home() / "AppData" / "Local"
		monkeypatch.setenv("LOCALAPPDATA", str(local))
		assert default_cache_root() == local / "srxy"
	else:
		assert default_cache_root() == Path.home() / ".cache" / "srxy"
	assert models_root() == default_cache_root()


def test_given_windows_when_resolving_non_prefix_cache_then_uses_localappdata(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.application import install_paths as paths

	monkeypatch.setattr(paths.platform, "system", lambda: "Windows")
	monkeypatch.delenv("SRXY_HOME", raising=False)
	monkeypatch.delenv("SRXY_CACHE_DIR", raising=False)
	local = tmp_path / "Local"
	monkeypatch.setenv("LOCALAPPDATA", str(local))

	# when / then
	assert paths.default_cache_root() == local / "srxy"


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


def test_given_home_when_default_install_prefix_then_uses_platform_default(
	monkeypatch: pytest.MonkeyPatch,
):
	# given / when / then
	import platform

	from srxy.application import install_paths as paths

	if platform.system().lower() == "windows":
		monkeypatch.setenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
		assert paths.default_install_prefix() == Path.home() / "AppData" / "Local" / "Programs" / "srxy"
	else:
		assert paths.default_install_prefix() == Path.home() / "Applications" / "srxy"
