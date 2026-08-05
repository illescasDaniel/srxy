from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.meta import load_installer_meta
from srxy.adapters.inbound.installer.package_spec import (
	parse_version_tuple,
	pypi_requires_pyside6,
	resolve_srxy_install_spec,
	version_at_least,
	version_newer,
)
from srxy.adapters.inbound.installer.path_setup import (
	PATH_BEGIN,
	PATH_END,
	ensure_path_block,
	remove_path_block,
)
from srxy.application.install_method import InstallMethod, detect_install_method, semantic_enable_hint
from srxy.application.updates import UpdateInfo, upgrade_command
from srxy.i18n import get_language, set_language, tr


pytestmark = pytest.mark.unit


def test_given_installer_meta_when_loaded_then_has_version_and_min_srxy():
	# given / when
	meta = load_installer_meta()

	# then
	assert meta.installer_version == "15"
	assert version_at_least(meta.min_srxy_version, "1.6.4")


def test_given_versions_when_comparing_then_orders_correctly():
	# given / when / then
	assert parse_version_tuple("1.6.0") == (1, 6, 0)
	assert version_newer("1.7.0", "1.6.0")
	assert not version_newer("1.6.0", "1.6.0")
	assert version_at_least("1.6.1", "1.6.0")
	assert not version_at_least("1.5.9", "1.6.0")


def test_given_pypi_info_without_pyside_when_checking_then_false():
	# given
	info = {"info": {"version": "1.5.0", "requires_dist": ["pillow>=1"]}}

	# when / then
	assert pypi_requires_pyside6(info, "1.5.0") is False


def test_given_pypi_info_with_pyside_when_checking_then_true():
	# given
	info = {"info": {"version": "1.6.0", "requires_dist": ["PySide6>=6.6", "pillow>=1"]}}

	# when / then
	assert pypi_requires_pyside6(info, "1.6.0") is True


def test_given_fetch_disabled_when_resolving_spec_then_uses_local(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_INSTALL_SPEC", raising=False)

	# when
	spec = resolve_srxy_install_spec(fetch_pypi=False)

	# then
	assert Path(spec).is_dir()


def test_given_shell_rc_when_writing_path_block_twice_then_idempotent(tmp_path: Path):
	# given
	rc = tmp_path / ".bashrc"
	bin_dir = tmp_path / "Applications" / "srxy" / "bin"
	bin_dir.mkdir(parents=True)

	# when
	ensure_path_block(bin_dir, shell_name="bash", rc_path=rc)
	ensure_path_block(bin_dir, shell_name="bash", rc_path=rc)
	text = rc.read_text(encoding="utf-8")

	# then
	assert text.count(PATH_BEGIN) == 1
	assert text.count(PATH_END) == 1
	assert str(bin_dir.resolve()) in text
	assert remove_path_block(rc).changed is True
	assert PATH_BEGIN not in rc.read_text(encoding="utf-8")


def test_given_srxy_home_manifest_when_detecting_method_then_desktop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_HOME", str(tmp_path))
	(tmp_path / ".srxy-manifest.json").write_text("{}", encoding="utf-8")

	# when / then
	assert detect_install_method(home=tmp_path) is InstallMethod.DESKTOP_PREFIX
	assert "installer" in semantic_enable_hint(InstallMethod.DESKTOP_PREFIX).lower()


def test_given_uv_tool_path_when_detecting_method_then_uv_tool(tmp_path: Path):
	# given
	exe = tmp_path / ".local" / "share" / "uv" / "tools" / "srxy" / "bin" / "python"
	exe.parent.mkdir(parents=True)
	exe.write_text("", encoding="utf-8")

	# when / then
	assert detect_install_method(home=None, executable=exe) is InstallMethod.UV_TOOL
	assert upgrade_command(InstallMethod.UV_TOOL)[1:3] == ["tool", "upgrade"]


def test_given_inno_language_names_when_resolving_then_maps_to_codes():
	from srxy.i18n import resolve_language

	assert resolve_language("english") == "en"
	assert resolve_language("spanish") == "es"
	assert resolve_language("en") == "en"
	assert resolve_language("es") == "es"


def test_given_spanish_catalog_when_translating_then_uses_es():
	# given
	set_language("es")

	# when / then
	assert get_language() == "es"
	assert "Ayuda" in tr("menu.help")
	set_language("en")
	assert tr("menu.help") == "Help"


def test_given_update_info_dataclass_when_created_then_holds_versions():
	# given / when
	info = UpdateInfo(
		current_version="1.6.0",
		latest_version="1.7.0",
		update_available=True,
		method=InstallMethod.PIP,
	)

	# then
	assert info.update_available
	assert "pip" in " ".join(upgrade_command(InstallMethod.PIP))
