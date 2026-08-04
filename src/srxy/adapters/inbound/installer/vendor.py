"""Install vendor binaries (uv, tesseract, ffmpeg) into the install prefix."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path

from srxy.adapters.inbound.installer.catalog import (
	DARWIN_ARM64_TESSERACT_BOTTLES,
	GHCR_BOTTLE_HEADERS,
	artifact,
)
from srxy.adapters.inbound.installer.download import (
	ProgressCallback,
	download_file,
	download_to_temp,
	extract_tar_archive,
	extract_zip_archive,
	move_tree,
)


_SYSTEM_DYLIB_PREFIXES = ("/usr/lib/", "/System/", "/Library/Apple/")


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


def _adhoc_codesign(path: Path):
	if platform.system().lower() != "darwin":
		return
	codesign = shutil.which("codesign")
	if codesign is None:
		return
	try:
		subprocess.run(  # noqa: S603
			[codesign, "--force", "--sign", "-", str(path)],
			check=True,
			capture_output=True,
			text=True,
		)
	except (OSError, subprocess.CalledProcessError):
		# Signing is best-effort; missing codesign should not block installs.
		pass


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
		_adhoc_codesign(target)
		try:
			subprocess.run([str(target), "--version"], check=True, capture_output=True, text=True)  # noqa: S603
		except OSError as exc:
			raise RuntimeError(
				"uv vendor binary is not executable on this machine "
				f"(system={platform.system()}, machine={platform.machine()}): {exc}"
			) from exc
		except subprocess.CalledProcessError as exc:
			raise RuntimeError(f"uv vendor binary failed self-check: {exc.stderr.strip() or exc}") from exc
		shutil.rmtree(extract_dir, ignore_errors=True)
		return target
	finally:
		archive.unlink(missing_ok=True)


def _install_tesseract_linux(prefix: Path, *, progress: ProgressCallback | None) -> Path:
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


def _is_system_dylib(dep: str) -> bool:
	return dep.startswith(_SYSTEM_DYLIB_PREFIXES)


def _otool_deps(path: Path) -> list[str]:
	otool = shutil.which("otool")
	if otool is None:
		raise RuntimeError("otool not found on PATH (required to relocate Darwin tesseract)")
	out = subprocess.check_output([otool, "-L", str(path)], text=True)  # noqa: S603
	return [line.strip().split(" ", 1)[0] for line in out.splitlines()[1:]]


def _index_bottle_dylibs(extract_root: Path) -> dict[str, list[Path]]:
	index: dict[str, list[Path]] = {}
	for path in extract_root.rglob("*.dylib"):
		if not path.is_file():
			continue
		index.setdefault(path.name, []).append(path)
	return index


def _resolve_bottle_dep(dep: str, *, referrer: Path, dylib_index: dict[str, list[Path]]) -> Path | None:
	if _is_system_dylib(dep):
		return None
	if dep.startswith("@loader_path/"):
		cand = (referrer.parent / dep[len("@loader_path/") :]).resolve()
		return cand if cand.is_file() else None
	if dep.startswith("@rpath/"):
		name = Path(dep[len("@rpath/") :]).name
		cands = dylib_index.get(name, [])
		return cands[0] if cands else None
	# Absolute paths and Homebrew @@HOMEBREW_*@@ placeholders: resolve by basename in bottles.
	name = Path(dep).name
	path = Path(dep)
	if not dep.startswith("@") and path.is_file():
		return path.resolve()
	cands = dylib_index.get(name, [])
	return cands[0] if cands else None


def _run_install_name_tool(*args: str):
	tool = shutil.which("install_name_tool")
	if tool is None:
		raise RuntimeError("install_name_tool not found on PATH (required to relocate Darwin tesseract)")
	subprocess.check_call([tool, *args])  # noqa: S603


def _rewrite_darwin_install_names(bin_path: Path, lib_dir: Path, copied: dict[str, str]):
	# Map both the staged soname and any original basename to the copied file name.
	by_base: dict[str, list[str]] = {}
	for orig, name in copied.items():
		by_base.setdefault(name, []).append(name)
		by_base.setdefault(Path(orig).name, []).append(name)

	def map_dep(dep: str) -> str | None:
		if _is_system_dylib(dep):
			return None
		path = Path(dep)
		if not dep.startswith("@") and path.is_file():
			key = str(path.resolve())
			if key in copied:
				return copied[key]
		cands = list(dict.fromkeys(by_base.get(path.name, [])))
		if len(cands) == 1:
			return cands[0]
		# Exact staged filename match.
		if (lib_dir / path.name).is_file():
			return path.name
		return None

	def rewrite(path: Path, *, for_binary: bool):
		if not for_binary:
			_run_install_name_tool("-id", f"@loader_path/{path.name}", str(path))
		for dep in _otool_deps(path):
			if _is_system_dylib(dep):
				continue
			if Path(dep).name == path.name and (dep.endswith(path.name) or "@@HOMEBREW" in dep):
				# Skip self-referential install names; -id already set for dylibs.
				if not for_binary:
					continue
			target_name = map_dep(dep)
			if target_name is None:
				if Path(dep).name == path.name:
					continue
				raise RuntimeError(f"cannot map dependency {dep} for {path}")
			new = f"@loader_path/../lib/{target_name}" if for_binary else f"@loader_path/{target_name}"
			if dep != new:
				_run_install_name_tool("-change", dep, new, str(path))

	for _orig, name in copied.items():
		rewrite(lib_dir / name, for_binary=False)
	rewrite(bin_path, for_binary=True)


def _reset_dir(path: Path):
	if path.exists():
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def _assemble_relocatable_tesseract(extract_root: Path, vendor: Path) -> Path:
	src_bin = _find_named_binary(extract_root, "tesseract")
	if src_bin is None:
		raise RuntimeError("tesseract binary missing from Homebrew bottles")

	bin_dir = vendor / "bin"
	lib_dir = vendor / "lib"
	tessdata = vendor / "tessdata"
	_reset_dir(bin_dir)
	_reset_dir(lib_dir)
	_reset_dir(tessdata)

	target = bin_dir / "tesseract"
	shutil.copy2(src_bin, target)
	_chmod_executable(target)

	dylib_index = _index_bottle_dylibs(extract_root)
	queue = [target]
	seen: set[str] = set()
	copied: dict[str, str] = {}

	while queue:
		current = queue.pop(0)
		for dep in _otool_deps(current):
			if _is_system_dylib(dep):
				continue
			src = _resolve_bottle_dep(dep, referrer=current, dylib_index=dylib_index)
			if src is None:
				if Path(dep).name == current.name:
					continue
				raise RuntimeError(f"unresolved tesseract dependency: {dep} (from {current})")
			# Prefer the install-name basename (often a stable symlink like libjpeg.8.dylib)
			# over the resolved versioned file name (libjpeg.8.3.2.dylib).
			link_name = Path(dep).name
			resolved = src.resolve()
			key = str(resolved)
			if key == str(target.resolve()):
				continue
			if key in seen:
				continue
			seen.add(key)
			name = link_name if (src.parent / link_name).exists() else src.name
			copy_src = src.parent / name if (src.parent / name).is_file() else src
			dest = lib_dir / name
			if dest.exists() and dest.read_bytes() != copy_src.read_bytes():
				name = f"{copy_src.parent.name}-{name}"
				dest = lib_dir / name
			# copy2 follows symlinks and writes a real file at the stable soname.
			shutil.copy2(copy_src, dest)
			_chmod_executable(dest)
			copied[key] = name
			queue.append(dest)

	_rewrite_darwin_install_names(target, lib_dir, copied)

	for path in sorted(lib_dir.glob("*.dylib")) + [target]:
		_adhoc_codesign(path)

	eng_candidates = list(extract_root.rglob("eng.traineddata"))
	if eng_candidates:
		shutil.copy2(eng_candidates[0], tessdata / "eng.traineddata")
	return target


def _ensure_eng_tessdata(vendor: Path, *, progress: ProgressCallback | None):
	eng = vendor / "tessdata" / "eng.traineddata"
	if eng.is_file():
		return
	data_item = artifact("tessdata_eng")
	eng.parent.mkdir(parents=True, exist_ok=True)
	download_file(
		data_item.url,
		eng,
		sha256=data_item.sha256,
		label="tessdata eng",
		progress=progress,
	)


def _self_check_tesseract(target: Path, tessdata: Path):
	env = os.environ.copy()
	env["TESSDATA_PREFIX"] = str(tessdata)
	env.pop("DYLD_LIBRARY_PATH", None)
	try:
		subprocess.run(  # noqa: S603
			[str(target), "--version"],
			check=True,
			capture_output=True,
			text=True,
			env=env,
		)
	except OSError as exc:
		raise RuntimeError(f"tesseract vendor binary is not executable: {exc}") from exc
	except subprocess.CalledProcessError as exc:
		raise RuntimeError(f"tesseract vendor binary failed self-check: {exc.stderr.strip() or exc}") from exc


def _install_tesseract_brew_bottles(prefix: Path, *, progress: ProgressCallback | None) -> Path:
	if platform.system().lower() != "darwin":
		raise RuntimeError("Homebrew bottle tesseract install is only supported on macOS")

	vendor = prefix / "vendor" / "tesseract"
	extract_root = vendor / "_bottles"
	if extract_root.exists():
		shutil.rmtree(extract_root)
	extract_root.mkdir(parents=True, exist_ok=True)

	try:
		for bottle in DARWIN_ARM64_TESSERACT_BOTTLES:
			archive = download_to_temp(
				bottle.url,
				suffix=".tar.gz",
				sha256=bottle.sha256,
				label=f"{bottle.formula} {bottle.version}",
				progress=progress,
				headers=GHCR_BOTTLE_HEADERS,
			)
			try:
				extract_tar_archive(archive, extract_root)
			finally:
				archive.unlink(missing_ok=True)

		target = _assemble_relocatable_tesseract(extract_root, vendor)
		_ensure_eng_tessdata(vendor, progress=progress)
		_self_check_tesseract(target, vendor / "tessdata")
		return target
	finally:
		shutil.rmtree(extract_root, ignore_errors=True)


def install_tesseract(prefix: Path, *, progress: ProgressCallback | None = None) -> Path:
	item = artifact("tesseract")
	if item.kind == "binary":
		return _install_tesseract_linux(prefix, progress=progress)
	if item.kind == "brew_bottles":
		return _install_tesseract_brew_bottles(prefix, progress=progress)
	raise RuntimeError(f"unsupported tesseract artifact kind: {item.kind}")


def _install_ffmpeg_tar(prefix: Path, *, progress: ProgressCallback | None) -> Path:
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


def _install_ffmpeg_zip(prefix: Path, *, progress: ProgressCallback | None) -> Path:
	item = artifact("ffmpeg")
	vendor = prefix / "vendor" / "ffmpeg"
	archive = download_to_temp(
		item.url,
		suffix=".zip",
		sha256=item.sha256,
		label=f"ffmpeg {item.version}",
		progress=progress,
	)
	try:
		extract_dir = vendor / "_extract"
		if extract_dir.exists():
			shutil.rmtree(extract_dir)
		extract_zip_archive(archive, extract_dir)
		binary = _find_named_binary(extract_dir, "ffmpeg")
		if binary is None:
			raise RuntimeError("ffmpeg binary missing from downloaded zip")
		bin_dir = vendor / "bin"
		bin_dir.mkdir(parents=True, exist_ok=True)
		target = bin_dir / "ffmpeg"
		if target.exists() or target.is_symlink():
			target.unlink()
		shutil.move(str(binary), str(target))
		_chmod_executable(target)
		_adhoc_codesign(target)
		shutil.rmtree(extract_dir, ignore_errors=True)
		return target
	finally:
		archive.unlink(missing_ok=True)


def install_ffmpeg(prefix: Path, *, progress: ProgressCallback | None = None) -> Path:
	item = artifact("ffmpeg")
	if item.kind == "archive":
		return _install_ffmpeg_tar(prefix, progress=progress)
	if item.kind == "zip":
		return _install_ffmpeg_zip(prefix, progress=progress)
	raise RuntimeError(f"unsupported ffmpeg artifact kind: {item.kind}")


__all__ = [
	"install_ffmpeg",
	"install_tesseract",
	"install_uv",
]
