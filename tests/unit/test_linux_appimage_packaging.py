"""Contract tests for Linux AppImage packaging (no full AppImage build)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.catalog import LINUX_X86_64_CATALOG
from srxy.adapters.inbound.installer.meta import load_installer_meta


pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_PACKAGING = _REPO / "packaging"
_LINUX = _PACKAGING / "linux-appimage"
_BOOTSTRAP = _PACKAGING / "online-bootstrap"
_META_PACKAGING = _PACKAGING / "installer_meta.toml"
_META_SRC = _REPO / "src" / "srxy" / "adapters" / "inbound" / "installer" / "installer_meta.toml"


def test_given_installer_meta_copies_when_comparing_then_match():
	# given
	packaging_text = _META_PACKAGING.read_text(encoding="utf-8")
	src_text = _META_SRC.read_text(encoding="utf-8")

	# when
	packaging = tomllib.loads(packaging_text)
	src = tomllib.loads(src_text)
	loaded = load_installer_meta()

	# then
	assert packaging == src
	assert packaging["installer_version"] == loaded.installer_version
	assert packaging["min_srxy_version"] == loaded.min_srxy_version


def test_given_linux_appimage_scripts_when_checking_layout_then_present_and_executable():
	# given
	scripts = [
		_LINUX / "build.sh",
		_LINUX / "build-online.sh",
		_LINUX / "smoke-appimage.sh",
		_LINUX / "smoke-appimage-online.sh",
		_LINUX / "prune_pyside.sh",
		_LINUX / "refresh_checksums.sh",
	]

	# when / then
	for path in scripts:
		assert path.is_file(), f"missing {path}"
		assert os.access(path, os.X_OK), f"not executable: {path}"
	assert (_LINUX / "README.md").is_file()


def test_given_offline_build_script_when_reading_then_names_offline_artifact():
	# given
	text = (_LINUX / "build.sh").read_text(encoding="utf-8")

	# when
	output_line = next(line for line in text.splitlines() if line.startswith("OUTPUT="))

	# then
	assert "installer-${INSTALLER_VERSION}" in output_line
	assert "installer-online" not in output_line
	assert "prune_pyside.sh" in text
	assert "UV_PYTHON_PREFERENCE=only-managed" in text


def test_given_online_build_script_when_reading_then_names_online_artifact_and_caps_icons():
	# given
	text = (_LINUX / "build-online.sh").read_text(encoding="utf-8")

	# when
	output_line = next(line for line in text.splitlines() if line.startswith("OUTPUT="))
	icon_loop = next(line for line in text.splitlines() if "for size in" in line)

	# then
	assert "installer-online-${INSTALLER_VERSION}" in output_line
	assert "srxy-online-bootstrap" in text
	assert "bootstrap-meta.json" in text
	assert "SHA256SUMS-online" in text
	assert "16 32 48 64 128 256" in icon_loop
	assert "512" not in icon_loop


def test_given_online_bootstrap_sources_when_checking_tree_then_required_files_exist():
	# given / when / then
	assert (_BOOTSTRAP / "go.mod").is_file()
	assert (_BOOTSTRAP / "main.go").is_file()
	assert (_BOOTSTRAP / "static" / "index.html").is_file()
	assert (_BOOTSTRAP / "static" / "app.js").is_file()
	assert (_BOOTSTRAP / "static" / "app.css").is_file()
	assert (_BOOTSTRAP / "internal" / "runtime" / "runtime.go").is_file()
	assert (_BOOTSTRAP / "internal" / "fetch" / "fetch.go").is_file()
	assert (_BOOTSTRAP / "internal" / "bootserver" / "server.go").is_file()


def test_given_uv_catalog_when_building_bootstrap_meta_shape_then_has_required_fields():
	# given
	uv = LINUX_X86_64_CATALOG["uv"]
	meta = load_installer_meta()

	# when
	payload = {
		"uv_url": uv.url,
		"uv_sha256": uv.sha256,
		"python_version": "3.12",
		"installer_version": meta.installer_version,
		"srxy_version": "1.6.0",
	}

	# then
	assert uv.url.startswith("https://")
	assert len(uv.sha256) == 64
	assert set(payload) == {
		"uv_url",
		"uv_sha256",
		"python_version",
		"installer_version",
		"srxy_version",
	}
	assert json.loads(json.dumps(payload)) == payload


def test_given_installer_icons_when_checking_online_sizes_then_present_through_256():
	# given
	icons = _REPO / "src" / "srxy" / "resources" / "icons"

	# when / then
	for size in (16, 32, 48, 64, 128, 256):
		path = icons / f"srxy-installer-{size}.png"
		assert path.is_file(), f"missing online AppImage icon: {path}"


def test_given_go_toolchain_when_running_online_bootstrap_tests_then_pass():
	# given
	go_bin = shutil.which("go")
	if go_bin is None:
		pytest.skip("go not installed")

	# when
	result = subprocess.run(  # noqa: S603 — trusted local go toolchain
		[go_bin, "test", "./..."],
		cwd=_BOOTSTRAP,
		capture_output=True,
		text=True,
		check=False,
		timeout=120,
	)

	# then
	assert result.returncode == 0, result.stdout + result.stderr
