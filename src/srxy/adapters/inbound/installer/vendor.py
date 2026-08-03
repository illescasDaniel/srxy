"""Install vendor binaries (uv, tesseract, ffmpeg) into the install prefix."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

from srxy.adapters.inbound.installer.catalog import artifact
from srxy.adapters.inbound.installer.download import (
	ProgressCallback,
	download_file,
	download_to_temp,
	extract_tar_archive,
	move_tree,
)


def _chmod_executable(path: Path):
	mode = path.stat().st_mode
	path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _find_named_binary(root: Path, name: str) -> Path | None:
	direct = root / name
	if direct.is_file():
		return direct
	for path in root.rglob(name):
		if path.is_file():
			return path
	return None


def install_uv(prefix: Path, *, progress: ProgressCallback | None = None) -> Path:
	item = artifact("uv")
	vendor = prefix / "vendor" / "uv"
	vendor.mkdir(parents=True, exist_ok=True)
	archive = download_to_temp(
		item.url,
		suffix=".tar.gz",
		sha256=item.sha256,
		label=f"uv {item.version}",
		progress=progress,
	)
	try:
		extract_dir = vendor / "_extract"
		if extract_dir.exists():
			shutil.rmtree(extract_dir)
		extract_tar_archive(archive, extract_dir)
		binary = _find_named_binary(extract_dir, "uv")
		if binary is None:
			raise RuntimeError("uv binary missing from downloaded archive")
		target = vendor / "uv"
		if target.exists():
			target.unlink()
		shutil.move(str(binary), str(target))
		_chmod_executable(target)
		shutil.rmtree(extract_dir, ignore_errors=True)
		return target
	finally:
		archive.unlink(missing_ok=True)


def install_tesseract(prefix: Path, *, progress: ProgressCallback | None = None) -> Path:
	binary_item = artifact("tesseract")
	data_item = artifact("tessdata_eng")
	vendor = prefix / "vendor" / "tesseract"
	bin_dir = vendor / "bin"
	tessdata = vendor / "tessdata"
	bin_dir.mkdir(parents=True, exist_ok=True)
	tessdata.mkdir(parents=True, exist_ok=True)

	target = bin_dir / "tesseract"
	download_file(
		binary_item.url,
		target,
		sha256=binary_item.sha256,
		label=f"tesseract {binary_item.version}",
		progress=progress,
	)
	_chmod_executable(target)

	eng = tessdata / "eng.traineddata"
	download_file(
		data_item.url,
		eng,
		sha256=data_item.sha256,
		label="tessdata eng",
		progress=progress,
	)
	return target


def install_ffmpeg(prefix: Path, *, progress: ProgressCallback | None = None) -> Path:
	item = artifact("ffmpeg")
	vendor = prefix / "vendor" / "ffmpeg"
	archive = download_to_temp(
		item.url,
		suffix=".tar.xz",
		sha256=item.sha256,
		label=f"ffmpeg {item.version}",
		progress=progress,
	)
	try:
		extract_dir = vendor / "_extract"
		if extract_dir.exists():
			shutil.rmtree(extract_dir)
		extract_tar_archive(archive, extract_dir)
		binary = _find_named_binary(extract_dir, "ffmpeg")
		if binary is None:
			raise RuntimeError("ffmpeg binary missing from downloaded archive")
		# Keep the extracted tree (shared libs) and expose bin/ffmpeg.
		# BtbN layout: ffmpeg-*/bin/ffmpeg + lib/
		package_root = binary.parent.parent if binary.parent.name == "bin" else binary.parent
		final = vendor / "dist"
		move_tree(package_root, final)
		shutil.rmtree(extract_dir, ignore_errors=True)
		link_bin = vendor / "bin"
		link_bin.mkdir(parents=True, exist_ok=True)
		target = link_bin / "ffmpeg"
		if target.exists() or target.is_symlink():
			target.unlink()
		os.symlink(final / "bin" / "ffmpeg" if (final / "bin" / "ffmpeg").exists() else final / "ffmpeg", target)
		_chmod_executable(target.resolve())
		return target
	finally:
		archive.unlink(missing_ok=True)


__all__ = [
	"install_ffmpeg",
	"install_tesseract",
	"install_uv",
]
