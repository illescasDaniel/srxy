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
from srxy.adapters.inbound.installer.resolve import (
	ResolvedArtifact,
	resolve_ffmpeg,
	resolve_tesseract,
	resolve_tesseract_brew_bottles,
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


def install_uv(prefix: Path, *, progress: ProgressCallback | None = None, cancel_file: str | None = None) -> Path:
	item = artifact("uv")
	vendor = prefix / "vendor" / "uv"
	vendor.mkdir(parents=True, exist_ok=True)
	is_zip = item.kind == "zip" or item.url.lower().endswith(".zip")
	archive = download_to_temp(
		item.url,
		suffix=".zip" if is_zip else ".tar.gz",
		sha256=item.sha256,
		label=f"uv {item.version}",
		progress=progress,
		cancel_file=cancel_file,
	)
	try:
		extract_dir = vendor / "_extract"
		if extract_dir.exists():
			shutil.rmtree(extract_dir)
		if is_zip:
			extract_zip_archive(archive, extract_dir)
		else:
			extract_tar_archive(archive, extract_dir)
		binary_names = ("uv.exe", "uv") if platform.system().lower() == "windows" else ("uv",)
		binary = None
		for name in binary_names:
			binary = _find_named_binary(extract_dir, name)
			if binary is not None:
				break
		if binary is None:
			raise RuntimeError("uv binary missing from downloaded archive")
		target_name = "uv.exe" if binary.name.lower().endswith(".exe") else "uv"
		target = vendor / target_name
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


def _install_tesseract_linux(
	prefix: Path,
	*,
	progress: ProgressCallback | None,
	tessdata_langs: tuple[str, ...] | None = None,
) -> Path:
	resolved = resolve_tesseract()
	vendor = prefix / "vendor" / "tesseract"
	bin_dir = vendor / "bin"
	tessdata = vendor / "tessdata"
	bin_dir.mkdir(parents=True, exist_ok=True)
	tessdata.mkdir(parents=True, exist_ok=True)

	target = bin_dir / "tesseract"
	download_file(
		resolved.url,
		target,
		sha256=resolved.sha256,
		label=f"tesseract {resolved.version}",
		progress=progress,
		require_digest=bool(resolved.sha256),
	)
	_chmod_executable(target)
	_ensure_tessdata_langs(vendor, tessdata_langs, progress=progress)
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
	# install_name_tool warns that edits invalidate code signatures; we re-sign
	# with an ad-hoc signature afterward. Capture stderr so the installer console
	# is not flooded with expected Xcode toolchain noise.
	result = subprocess.run(  # noqa: S603
		[tool, *args],
		check=False,
		capture_output=True,
		text=True,
	)
	if result.returncode != 0:
		detail = (result.stderr or result.stdout or "").strip() or f"exit {result.returncode}"
		raise RuntimeError(f"install_name_tool {' '.join(args)} failed: {detail}")


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


def _ensure_tessdata_langs(
	vendor: Path,
	langs: tuple[str, ...] | list[str] | None,
	*,
	progress: ProgressCallback | None,
):
	from srxy.adapters.inbound.installer.tessdata_langs import (
		normalize_tessdata_langs,
		tessdata_artifact,
		tessdata_dest_path,
	)

	tessdata = vendor / "tessdata"
	tessdata.mkdir(parents=True, exist_ok=True)
	for code in normalize_tessdata_langs(langs):
		dest = tessdata_dest_path(tessdata, code)
		if dest.is_file():
			continue
		dest.parent.mkdir(parents=True, exist_ok=True)
		item = tessdata_artifact(code)
		download_file(
			item.url,
			dest,
			sha256=item.sha256,
			label=f"tessdata {code}",
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


def _install_tesseract_brew_bottles(
	prefix: Path,
	*,
	progress: ProgressCallback | None,
	tessdata_langs: tuple[str, ...] | None = None,
) -> Path:
	if platform.system().lower() != "darwin":
		raise RuntimeError("Homebrew bottle tesseract install is only supported on macOS")

	vendor = prefix / "vendor" / "tesseract"
	extract_root = vendor / "_bottles"
	if extract_root.exists():
		shutil.rmtree(extract_root)
	extract_root.mkdir(parents=True, exist_ok=True)

	machine = platform.machine().lower()
	try:
		bottles = resolve_tesseract_brew_bottles()
	except RuntimeError:
		if machine in {"arm64", "arm64e"}:
			bottles = DARWIN_ARM64_TESSERACT_BOTTLES
		else:
			raise

	try:
		for bottle in bottles:
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
		_ensure_tessdata_langs(vendor, tessdata_langs, progress=progress)
		_self_check_tesseract(target, vendor / "tessdata")
		return target
	finally:
		shutil.rmtree(extract_root, ignore_errors=True)


def _run_checked(cmd: list[str], *, cwd: Path | None = None, label: str) -> None:
	result = subprocess.run(  # noqa: S603
		cmd,
		check=False,
		capture_output=True,
		text=True,
		cwd=str(cwd) if cwd is not None else None,
	)
	if result.returncode != 0:
		detail = (result.stderr or result.stdout or "").strip()
		raise RuntimeError(f"{label} failed ({result.returncode}): {detail}")


def _prepare_7zip_extractor(work_dir: Path, *, progress: ProgressCallback | None) -> Path:
	"""Download pinned 7zr + 7-Zip SFX and return ``7z.exe`` (with ``7z.dll`` beside it)."""
	sevenzr_item = artifact("7zr")
	sevenzip_item = artifact("7zip")
	tools = work_dir / "_7zip"
	if tools.exists():
		shutil.rmtree(tools)
	tools.mkdir(parents=True, exist_ok=True)

	sevenzr = download_to_temp(
		sevenzr_item.url,
		suffix=".exe",
		sha256=sevenzr_item.sha256,
		label=f"7zr {sevenzr_item.version}",
		progress=progress,
	)
	sfx = download_to_temp(
		sevenzip_item.url,
		suffix=".exe",
		sha256=sevenzip_item.sha256,
		label=f"7zip {sevenzip_item.version}",
		progress=progress,
	)
	try:
		_run_checked(
			[str(sevenzr), "x", str(sfx), f"-o{tools}", "-y"],
			label="7zr extract 7-Zip package",
		)
		sevenz = tools / "7z.exe"
		if not sevenz.is_file() or not (tools / "7z.dll").is_file():
			raise RuntimeError("7z.exe/7z.dll missing after extracting the 7-Zip package")
		return sevenz
	finally:
		sevenzr.unlink(missing_ok=True)
		sfx.unlink(missing_ok=True)


def _layout_windows_tesseract_extract(extract_root: Path, vendor: Path) -> Path:
	"""Move ``tesseract.exe`` + DLLs into ``vendor/bin`` and ``tessdata`` into ``vendor/tessdata``."""
	plugins = extract_root / "$PLUGINSDIR"
	if plugins.exists():
		shutil.rmtree(plugins, ignore_errors=True)

	target = _find_named_binary(extract_root, "tesseract.exe")
	if target is None:
		raise RuntimeError("tesseract.exe missing after extracting Windows NSIS setup")

	tessdata_src = extract_root / "tessdata"
	if not tessdata_src.is_dir():
		for eng in extract_root.rglob("eng.traineddata"):
			tessdata_src = eng.parent
			break

	bin_dir = vendor / "bin"
	if bin_dir.exists():
		shutil.rmtree(bin_dir)
	bin_dir.mkdir(parents=True, exist_ok=True)

	# Keep DLLs beside the exe so the Windows loader finds them without admin PATH changes.
	link = bin_dir / "tesseract.exe"
	shutil.move(str(target), str(link))
	for dll in extract_root.glob("*.dll"):
		shutil.move(str(dll), str(bin_dir / dll.name))

	tessdata = vendor / "tessdata"
	if tessdata.exists():
		shutil.rmtree(tessdata)
	if tessdata_src.is_dir():
		shutil.move(str(tessdata_src), str(tessdata))
	else:
		tessdata.mkdir(parents=True, exist_ok=True)

	return link


def _install_tesseract_nsis(
	prefix: Path,
	*,
	progress: ProgressCallback | None,
	tessdata_langs: tuple[str, ...] | None = None,
) -> Path:
	"""Extract the UB-Mannheim NSIS setup into ``prefix/vendor/tesseract`` without elevation."""
	resolved = resolve_tesseract()
	vendor = prefix / "vendor" / "tesseract"
	if vendor.exists():
		shutil.rmtree(vendor)
	vendor.mkdir(parents=True, exist_ok=True)

	work_dir = vendor / "_work"
	work_dir.mkdir(parents=True, exist_ok=True)
	installer = download_to_temp(
		resolved.url,
		suffix=".exe",
		sha256=resolved.sha256,
		label=f"tesseract {resolved.version}",
		progress=progress,
		require_digest=bool(resolved.sha256),
	)
	try:
		sevenz = _prepare_7zip_extractor(work_dir, progress=progress)
		extract_root = work_dir / "nsis"
		if extract_root.exists():
			shutil.rmtree(extract_root)
		extract_root.mkdir(parents=True, exist_ok=True)
		# Never CreateProcess the setup EXE (WinError 740 / requireAdministrator).
		_run_checked(
			[str(sevenz), "x", str(installer), f"-o{extract_root}", "-y"],
			cwd=sevenz.parent,
			label="7z extract tesseract NSIS setup",
		)
		link = _layout_windows_tesseract_extract(extract_root, vendor)
		_ensure_tessdata_langs(vendor, tessdata_langs, progress=progress)
		_self_check_tesseract(link, vendor / "tessdata")
		return link
	finally:
		installer.unlink(missing_ok=True)
		shutil.rmtree(work_dir, ignore_errors=True)


def install_tesseract(
	prefix: Path,
	*,
	progress: ProgressCallback | None = None,
	tessdata_langs: tuple[str, ...] | None = None,
) -> Path:
	item = artifact("tesseract")
	if item.kind == "binary":
		return _install_tesseract_linux(prefix, progress=progress, tessdata_langs=tessdata_langs)
	if item.kind == "brew_bottles":
		return _install_tesseract_brew_bottles(prefix, progress=progress, tessdata_langs=tessdata_langs)
	if item.kind == "nsis_installer":
		return _install_tesseract_nsis(prefix, progress=progress, tessdata_langs=tessdata_langs)
	raise RuntimeError(f"unsupported tesseract artifact kind: {item.kind}")


def _expose_ffmpeg_bin(vendor: Path, binary: Path) -> Path:
	"""Point ``vendor/bin/ffmpeg[.exe]`` at the real binary without requiring symlinks."""
	bin_dir = vendor / "bin"
	bin_dir.mkdir(parents=True, exist_ok=True)
	target_name = "ffmpeg.exe" if binary.name.lower().endswith(".exe") else "ffmpeg"
	target = bin_dir / target_name
	if target.exists() or target.is_symlink():
		target.unlink()
	# Windows: never symlink here. CreateProcess/path resolve across vendor symlinks can
	# raise WinError 448 (ERROR_UNTRUSTED_MOUNT_POINT) under current Windows hardening.
	if platform.system().lower() == "windows":
		shutil.copy2(binary, target)
	else:
		try:
			os.symlink(binary, target)
		except OSError:
			shutil.copy2(binary, target)
	_chmod_executable(target.resolve() if target.is_symlink() else target)
	return target


def _install_ffmpeg_tar(
	prefix: Path,
	*,
	progress: ProgressCallback | None,
	resolved: ResolvedArtifact | None = None,
) -> Path:
	item = resolved if resolved is not None else resolve_ffmpeg()
	vendor = prefix / "vendor" / "ffmpeg"
	archive = download_to_temp(
		item.url,
		suffix=".tar.xz",
		sha256=item.sha256,
		label=f"ffmpeg {item.version}",
		progress=progress,
		require_digest=bool(item.sha256),
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
		real = final / "bin" / "ffmpeg" if (final / "bin" / "ffmpeg").exists() else final / "ffmpeg"
		return _expose_ffmpeg_bin(vendor, real)
	finally:
		archive.unlink(missing_ok=True)


def _install_ffmpeg_zip(
	prefix: Path,
	*,
	progress: ProgressCallback | None,
	resolved: ResolvedArtifact | None = None,
) -> Path:
	item = resolved if resolved is not None else resolve_ffmpeg()
	vendor = prefix / "vendor" / "ffmpeg"
	archive = download_to_temp(
		item.url,
		suffix=".zip",
		sha256=item.sha256,
		label=f"ffmpeg {item.version}",
		progress=progress,
		require_digest=bool(item.sha256),
	)
	try:
		extract_dir = vendor / "_extract"
		if extract_dir.exists():
			shutil.rmtree(extract_dir)
		extract_zip_archive(archive, extract_dir)
		names = ("ffmpeg.exe", "ffmpeg") if platform.system().lower() == "windows" else ("ffmpeg",)
		binary = None
		for name in names:
			binary = _find_named_binary(extract_dir, name)
			if binary is not None:
				break
		if binary is None:
			raise RuntimeError("ffmpeg binary missing from downloaded zip")
		# BtbN Windows shared builds need the whole tree (bin + lib next to each other).
		if binary.parent.name.lower() == "bin":
			package_root = binary.parent.parent
			final = vendor / "dist"
			if final.exists():
				shutil.rmtree(final)
			move_tree(package_root, final)
			shutil.rmtree(extract_dir, ignore_errors=True)
			real = final / "bin" / binary.name
			return _expose_ffmpeg_bin(vendor, real)
		bin_dir = vendor / "bin"
		bin_dir.mkdir(parents=True, exist_ok=True)
		target = bin_dir / binary.name
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
	resolved = resolve_ffmpeg()
	if resolved.kind == "archive":
		return _install_ffmpeg_tar(prefix, progress=progress, resolved=resolved)
	if resolved.kind == "zip":
		return _install_ffmpeg_zip(prefix, progress=progress, resolved=resolved)
	raise RuntimeError(f"unsupported ffmpeg artifact kind: {resolved.kind}")


__all__ = [
	"install_ffmpeg",
	"install_tesseract",
	"install_uv",
]
