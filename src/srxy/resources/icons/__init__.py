"""Application icon paths shipped with srxy."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def icon_dir() -> Path:
	return Path(str(resources.files("srxy.resources.icons")))


def app_icon_path(*, size: int | None = None) -> Path:
	"""Return packaged PNG path. ``size`` picks ``srxy-<size>.png`` when present."""
	directory = icon_dir()
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
	raise FileNotFoundError("srxy application icon is missing from package data")


def available_icon_sizes() -> list[int]:
	sizes: list[int] = []
	for path in icon_dir().glob("srxy-*.png"):
		stem = path.stem.removeprefix("srxy-")
		if stem.isdigit():
			sizes.append(int(stem))
	return sorted(sizes)


__all__ = [
	"app_icon_path",
	"available_icon_sizes",
	"icon_dir",
]
