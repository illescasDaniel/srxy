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
_WHEEL_ENV = "SRXY_INSTALL_WHEEL"
_SPEC_ENV = "SRXY_INSTALL_SPEC"


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
	# Windows Inno offline payload (and optional SRXY_INSTALLER_PAYLOAD root).
	payload = os.environ.get("SRXY_INSTALLER_PAYLOAD", "").strip()
	if payload:
		share = Path(payload) / "share" / "srxy"
		candidates.extend(sorted(share.glob("srxy-*.whl"), reverse=True))
		candidates.append(share / "srxy.whl")
	# Relative to the frozen/bootstrap tree: share/srxy next to the installer package.
	here = Path(__file__).resolve().parent
	candidates.extend(sorted((here / "wheels").glob("srxy-*.whl"), reverse=True))
	# packaging layout: <payload>/share/srxy when running from bootstrap venv site-packages
	# that still has a sibling share directory at the payload root.
	for parent in here.parents:
		share = parent / "share" / "srxy"
		if share.is_dir():
			candidates.extend(sorted(share.glob("srxy-*.whl"), reverse=True))
			candidates.append(share / "srxy.whl")
			break
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


def resolve_install_wheel_env() -> str | None:
	"""Return an absolute wheel path from ``SRXY_INSTALL_WHEEL``, or None if unset.

	Raises ``ValueError`` when the env var is set but the path is missing or not a ``.whl``.
	"""
	raw = os.environ.get(_WHEEL_ENV, "").strip()
	if not raw:
		return None
	path = Path(raw).expanduser().resolve()
	if not path.is_file():
		raise ValueError(f"{_WHEEL_ENV}={raw!r} does not exist or is not a file")
	if path.suffix.lower() != ".whl":
		raise ValueError(f"{_WHEEL_ENV}={raw!r} must be a .whl file")
	return str(path)


def _override_install_spec() -> str | None:
	"""Prefer ``SRXY_INSTALL_WHEEL``, then ``SRXY_INSTALL_SPEC``."""
	wheel = resolve_install_wheel_env()
	if wheel is not None:
		return wheel
	override = os.environ.get(_SPEC_ENV, "").strip()
	return override or None


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
	override = _override_install_spec()
	if override is not None:
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

	Honors ``SRXY_INSTALL_WHEEL`` then ``SRXY_INSTALL_SPEC`` when set. Requires a
	PyPI release that meets ``min_srxy_version`` and lists PySide6 when ``fetch_pypi``
	is true.
	"""
	override = _override_install_spec()
	if override is not None:
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


def _is_local_path_spec(spec: str) -> bool:
	"""True when ``spec`` looks like a filesystem path (wheel, sdist, or source tree)."""
	text = spec.strip()
	if not text or "://" in text or " @ " in text:
		return False
	if text.endswith(".whl") or text.endswith(".tar.gz") or text.endswith(".zip"):
		return True
	if text.startswith(("/", "./", "../", "~")):
		return True
	# Absolute Windows path (C:\...) — keep portable without importing platform helpers.
	if len(text) >= 3 and text[1] == ":" and text[0].isalpha():
		return True
	candidate = Path(text).expanduser()
	return candidate.exists()


def with_extras(spec: str, *extras: str) -> str:
	"""Insert extras into a PEP 508 requirement (before any version pin).

	Local wheel/path specs become ``srxy[extra,...] @ file:///...`` so ``uv pip``
	accepts extras with a local artifact. Existing extras are merged (order preserved).
	"""
	wanted: list[str] = []
	for extra in extras:
		name = extra.strip()
		if name and name not in wanted:
			wanted.append(name)
	text = spec.strip()
	if not wanted:
		return text

	# Already has ``name[extras]...`` (including ``name[extras] @ uri``).
	bracket = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\[([^\]]*)\](.*)$", text)
	if bracket is not None:
		existing = [part.strip() for part in bracket.group(2).split(",") if part.strip()]
		merged = existing[:]
		for name in wanted:
			if name not in merged:
				merged.append(name)
		return f"{bracket.group(1)}[{','.join(merged)}]{bracket.group(3)}"

	extra_clause = ",".join(wanted)
	if _is_local_path_spec(text):
		path = Path(text).expanduser().resolve()
		return f"srxy[{extra_clause}] @ {path.as_uri()}"
	# name==1.2.3 / name>=1.2 / name~=1.2.3 — extras must precede the version clause.
	match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\s*(?:[<>=!~]=?|===).+)$", text)
	if match is not None:
		return f"{match.group(1)}[{extra_clause}]{match.group(2)}"
	return f"{text}[{extra_clause}]"


def with_semantic_extra(spec: str) -> str:
	"""Insert ``[semantic]`` into a PEP 508 requirement (before any version pin)."""
	return with_extras(spec, "semantic")


def with_windows_extra(spec: str) -> str:
	"""Insert ``[windows]`` into a PEP 508 requirement (before any version pin)."""
	return with_extras(spec, "windows")


__all__ = [
	"fetch_pypi_srxy_info",
	"local_source_version",
	"parse_version_tuple",
	"pypi_latest_version",
	"pypi_requires_pyside6",
	"resolve_bundled_or_local_spec",
	"resolve_install_wheel_env",
	"resolve_pypi_install_spec",
	"resolve_srxy_install_spec",
	"version_at_least",
	"version_newer",
	"wheel_version_from_path",
	"with_extras",
	"with_semantic_extra",
	"with_windows_extra",
]
