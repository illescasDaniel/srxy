"""Application icon paths shipped with srxy."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def icon_dir() -> Path:
	return Path(str(resources.files("srxy.resources.icons")))


def _resolve_icon(*, prefix: str, size: int | None, missing: str) -> Path:
	directory = icon_dir()
	if size is not None:
		sized = directory / f"{prefix}-{size}.png"
		if sized.is_file():
			return sized
	primary = directory / f"{prefix}.png"
	if primary.is_file():
		return primary
	fallback = directory / f"{prefix}-256.png"
	if fallback.is_file():
		return fallback
	raise FileNotFoundError(missing)


def _available_sizes(prefix: str) -> list[int]:
	sizes: list[int] = []
	needle = f"{prefix}-"
	for path in icon_dir().glob(f"{prefix}-*.png"):
		stem = path.stem.removeprefix(needle)
		if stem.isdigit():
			sizes.append(int(stem))
	return sorted(sizes)


def app_icon_path(*, size: int | None = None) -> Path:
	"""Return packaged PNG path. ``size`` picks ``srxy-<size>.png`` when present."""
	return _resolve_icon(
		prefix="srxy",
		size=size,
		missing="srxy application icon is missing from package data",
	)


def _resolve_macos_icon(*, size: int | None) -> Path:
	directory = icon_dir() / "macos"
	if size is not None:
		sized = directory / f"srxy-{size}.png"
		if sized.is_file():
			return sized
	primary = directory / "srxy.png"
	if primary.is_file():
		return primary
	fallback = directory / "srxy-256.png"
	if fallback.is_file():
		return fallback
	raise FileNotFoundError(f"srxy macOS icon missing under {directory}")


def macos_app_icon_path(*, size: int | None = None) -> Path:
	"""Return squircle-masked PNG for ``Srxy.app`` / ``.icns`` (transparent corners).

	Falls back to the square ``app_icon_path`` when the macos/ tree is missing
	(e.g. incomplete checkout); prefer regenerating via ``task generate-macos-icons``.
	"""
	try:
		return _resolve_macos_icon(size=size)
	except FileNotFoundError:
		return app_icon_path(size=size)


def installer_icon_path(*, size: int | None = None) -> Path:
	"""Return packaged installer PNG. ``size`` picks ``srxy-installer-<size>.png``."""
	return _resolve_icon(
		prefix="srxy-installer",
		size=size,
		missing="srxy installer icon is missing from package data",
	)


def available_icon_sizes() -> list[int]:
	return _available_sizes("srxy")


def available_installer_icon_sizes() -> list[int]:
	return _available_sizes("srxy-installer")


def available_macos_icon_sizes() -> list[int]:
	directory = icon_dir() / "macos"
	if not directory.is_dir():
		return []
	sizes: list[int] = []
	for path in directory.glob("srxy-*.png"):
		stem = path.stem.removeprefix("srxy-")
		if stem.isdigit():
			sizes.append(int(stem))
	return sorted(sizes)


__all__ = [
	"app_icon_path",
	"available_icon_sizes",
	"available_installer_icon_sizes",
	"available_macos_icon_sizes",
	"icon_dir",
	"installer_icon_path",
	"macos_app_icon_path",
]
