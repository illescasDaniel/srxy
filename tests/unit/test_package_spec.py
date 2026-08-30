from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.package_spec import (
	resolve_install_wheel_env,
	resolve_pypi_install_spec,
	resolve_srxy_install_spec,
	with_extras,
	with_semantic_extra,
)


pytestmark = pytest.mark.unit


def test_given_source_checkout_when_resolving_spec_then_uses_project_root():
	# given / when
	spec = resolve_srxy_install_spec()

	# then
	assert Path(spec).is_dir()
	assert (Path(spec) / "pyproject.toml").is_file()


def test_given_named_spec_when_adding_semantic_then_appends_extra():
	# given / when / then
	assert with_semantic_extra("srxy") == "srxy[semantic]"
	assert with_semantic_extra("srxy[semantic]") == "srxy[semantic]"


def test_given_local_path_when_adding_semantic_then_uses_pep508_url(tmp_path: Path):
	# given — directory path (source tree style)
	root = tmp_path / "srxy"
	root.mkdir()

	# when
	result = with_semantic_extra(str(root))

	# then
	assert result == f"srxy[semantic] @ {root.resolve().as_uri()}"


def test_given_wheel_path_when_adding_semantic_then_uses_pep508_url(tmp_path: Path):
	# given
	wheel = tmp_path / "srxy-1.6.2-py3-none-any.whl"
	wheel.write_bytes(b"PK")

	# when
	result = with_semantic_extra(str(wheel))

	# then
	assert result == f"srxy[semantic] @ {wheel.resolve().as_uri()}"


def test_given_versioned_spec_when_adding_semantic_then_inserts_extra_before_pin():
	# given / when / then — PEP 508 requires name[extra]==version, not name==version[extra]
	assert with_semantic_extra("srxy==1.6.0") == "srxy[semantic]==1.6.0"
	assert with_semantic_extra("srxy>=1.6.0,<2") == "srxy[semantic]>=1.6.0,<2"


def test_given_host_when_resolving_package_extras_then_only_semantic_when_requested(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.adapters.inbound.installer import install as install_mod

	monkeypatch.setattr(install_mod, "_is_windows", lambda: True)

	# when / then — pywin32 is core on Windows; no [windows] extra
	assert install_mod.package_extras_for_host(install_semantic=False) == []
	assert install_mod.package_extras_for_host(install_semantic=True) == ["semantic"]

	monkeypatch.setattr(install_mod, "_is_windows", lambda: False)
	assert install_mod.package_extras_for_host(install_semantic=True) == ["semantic"]
	assert install_mod.package_extras_for_host(install_semantic=False) == []


def test_given_windows_host_when_composing_install_spec_then_applies_semantic_only(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer import install as install_mod

	monkeypatch.setattr(install_mod, "_is_windows", lambda: True)
	wheel = tmp_path / "srxy-1.6.4-py3-none-any.whl"
	wheel.write_bytes(b"PK")
	spec = str(wheel)

	# when
	extras = install_mod.package_extras_for_host(install_semantic=True)
	composed = with_extras(spec, *extras)

	# then
	assert extras == ["semantic"]
	assert composed == f"srxy[semantic] @ {wheel.resolve().as_uri()}"


def test_given_env_override_when_resolving_spec_then_uses_override(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_INSTALL_WHEEL", raising=False)
	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==9.9.9")

	# when / then
	assert resolve_srxy_install_spec() == "srxy==9.9.9"
	assert resolve_pypi_install_spec() == "srxy==9.9.9"


def test_given_install_wheel_env_when_resolving_then_prefers_wheel_over_spec(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	wheel = tmp_path / "srxy-9.9.9-py3-none-any.whl"
	wheel.write_bytes(b"PK")
	monkeypatch.setenv("SRXY_INSTALL_WHEEL", str(wheel))
	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==1.0.0")

	# when
	spec = resolve_pypi_install_spec()
	offline = resolve_srxy_install_spec()

	# then
	assert spec == str(wheel.resolve())
	assert offline == str(wheel.resolve())
	assert resolve_install_wheel_env() == str(wheel.resolve())


def test_given_missing_install_wheel_when_resolving_then_raises(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	missing = tmp_path / "missing.whl"
	monkeypatch.setenv("SRXY_INSTALL_WHEEL", str(missing))

	# when / then
	with pytest.raises(ValueError, match="does not exist"):
		resolve_install_wheel_env()


def test_given_non_wheel_install_wheel_when_resolving_then_raises(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	path = tmp_path / "srxy.tar.gz"
	path.write_bytes(b"data")
	monkeypatch.setenv("SRXY_INSTALL_WHEEL", str(path))

	# when / then
	with pytest.raises(ValueError, match="must be a .whl"):
		resolve_install_wheel_env()
