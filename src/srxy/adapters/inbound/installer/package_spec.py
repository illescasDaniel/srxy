"""Resolve which srxy package the installer should install into the prefix."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path

from srxy.adapters.inbound.installer.meta import load_installer_meta


_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _project_root_from_package() -> Path | None:
	# install.py → installer → inbound → adapters → srxy → src → repo root
	root = Path(__file__).resolve().parents[5]
	pyproject = root / "pyproject.toml"
	if not pyproject.is_file():
		return None
	try:
		text = pyproject.read_text(encoding="utf-8")
	except OSError:
		return None
	if 'name = "srxy"' not in text and "name = 'srxy'" not in text:
		return None
	return root


def _bundled_wheel_candidates() -> list[Path]:
	candidates: list[Path] = []
	appdir = os.environ.get("APPDIR", "").strip()
	if appdir:
		share = Path(appdir) / "usr" / "share" / "srxy"
		candidates.extend(sorted(share.glob("srxy-*.whl"), reverse=True))
		candidates.append(share / "srxy.whl")
	here = Path(__file__).resolve().parent
	candidates.extend(sorted((here / "wheels").glob("srxy-*.whl"), reverse=True))
	return candidates


def parse_version_tuple(version: str) -> tuple[int, int, int] | None:
	match = _VERSION_RE.search(version.strip())
	if match is None:
		return None
	return int(match.group(1)), int(match.group(2)), int(match.group(3))


def version_at_least(version: str, minimum: str) -> bool:
	left = parse_version_tuple(version)
	right = parse_version_tuple(minimum)
	if left is None or right is None:
		return False
	return left >= right


def version_newer(candidate: str, baseline: str) -> bool:
	left = parse_version_tuple(candidate)
	right = parse_version_tuple(baseline)
	if left is None or right is None:
		return False
	return left > right


def wheel_version_from_path(path: Path) -> str | None:
	# srxy-1.6.0-py3-none-any.whl
	match = re.match(r"srxy-([0-9][^-]+)", path.name)
	if match is None:
		return None
	return match.group(1)


def local_source_version(root: Path) -> str | None:
	pyproject = root / "pyproject.toml"
	if not pyproject.is_file():
		return None
	try:
		text = pyproject.read_text(encoding="utf-8")
	except OSError:
		return None
	match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
	if match is None:
		return None
	return match.group(1)


def fetch_pypi_srxy_info(*, timeout: float = 15.0) -> dict[str, object] | None:
	url = "https://pypi.org/pypi/srxy/json"
	request = urllib.request.Request(url, headers={"User-Agent": "srxy-installer"})
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
			payload = json.loads(response.read().decode("utf-8"))
	except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
		return None
	if not isinstance(payload, dict):
		return None
	return payload


def pypi_latest_version(info: Mapping[str, object]) -> str | None:
	info_block = info.get("info")
	if not isinstance(info_block, dict):
		return None
	version = info_block.get("version")
	return str(version) if version else None


def pypi_requires_pyside6(info: Mapping[str, object], version: str) -> bool:
	"""True when the given release lists PySide6 in requires_dist (or latest info)."""
	releases = info.get("releases")
	# Prefer requires_dist on the info object when version matches latest.
	info_block = info.get("info")
	if isinstance(info_block, dict) and str(info_block.get("version", "")) == version:
		requires = info_block.get("requires_dist") or []
		if isinstance(requires, list):
			for item in requires:
				text = str(item).lower()
				if text.startswith("pyside6"):
					return True
	# Fallback: inspect release URLs metadata is not always present; use info requires.
	if isinstance(info_block, dict):
		requires = info_block.get("requires_dist") or []
		if isinstance(requires, list) and any(str(item).lower().startswith("pyside6") for item in requires):
			# Only trust if we are looking at the same latest version.
			if str(info_block.get("version", "")) == version:
				return True
	_ = releases
	return False


def resolve_bundled_or_local_spec() -> tuple[str, str | None]:
	"""Return (spec, version_or_none) for bundled wheel or local source."""
	for wheel in _bundled_wheel_candidates():
		if wheel.is_file():
			return str(wheel.resolve()), wheel_version_from_path(wheel)
	root = _project_root_from_package()
	if root is not None:
		return str(root), local_source_version(root)
	return "srxy", None


def resolve_srxy_install_spec(*, fetch_pypi: bool = True) -> str:
	"""Prefer newer compatible PyPI when safe; otherwise bundled/local/PyPI name."""
	override = os.environ.get("SRXY_INSTALL_SPEC", "").strip()
	if override:
		return override

	bundled_spec, bundled_version = resolve_bundled_or_local_spec()
	meta = load_installer_meta()

	if not fetch_pypi:
		return bundled_spec

	info = fetch_pypi_srxy_info()
	if info is None:
		return bundled_spec
	latest = pypi_latest_version(info)
	if latest is None:
		return bundled_spec
	if not version_at_least(latest, meta.min_srxy_version):
		return bundled_spec
	if not pypi_requires_pyside6(info, latest):
		return bundled_spec
	if bundled_version is not None and not version_newer(latest, bundled_version):
		return bundled_spec
	# Bundled is a path/wheel — prefer PyPI only when newer than that baseline.
	if bundled_version is None and bundled_spec == "srxy":
		return f"srxy=={latest}"
	if bundled_version is not None and version_newer(latest, bundled_version):
		return f"srxy=={latest}"
	return bundled_spec


def resolve_pypi_install_spec(*, fetch_pypi: bool = True) -> str:
	"""Always install from PyPI (online installer). Never uses a bundled wheel.

	Honors ``SRXY_INSTALL_SPEC`` when set. Requires a PyPI release that meets
	``min_srxy_version`` and lists PySide6 when ``fetch_pypi`` is true.
	"""
	override = os.environ.get("SRXY_INSTALL_SPEC", "").strip()
	if override:
		return override

	meta = load_installer_meta()
	if not fetch_pypi:
		return "srxy"

	info = fetch_pypi_srxy_info()
	if info is None:
		raise RuntimeError("Could not reach PyPI to resolve the srxy package version.")
	latest = pypi_latest_version(info)
	if latest is None:
		raise RuntimeError("PyPI did not report a latest srxy version.")
	if not version_at_least(latest, meta.min_srxy_version):
		raise RuntimeError(f"PyPI srxy {latest} is older than this installer requires ({meta.min_srxy_version}).")
	if not pypi_requires_pyside6(info, latest):
		raise RuntimeError(f"PyPI srxy {latest} does not list PySide6; refusing to install.")
	return f"srxy=={latest}"


def with_semantic_extra(spec: str) -> str:
	"""Append ``[semantic]`` when installing from a path/wheel/name."""
	if "[" in spec:
		return spec
	return f"{spec}[semantic]"


__all__ = [
	"fetch_pypi_srxy_info",
	"local_source_version",
	"parse_version_tuple",
	"pypi_latest_version",
	"pypi_requires_pyside6",
	"resolve_bundled_or_local_spec",
	"resolve_pypi_install_spec",
	"resolve_srxy_install_spec",
	"version_at_least",
	"version_newer",
	"wheel_version_from_path",
	"with_semantic_extra",
]
