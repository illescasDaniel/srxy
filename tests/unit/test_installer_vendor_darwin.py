"""Unit tests for installer vendor catalog and Darwin brew-bottle install."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from srxy.adapters.inbound.installer import catalog as catalog_mod, vendor as vendor_mod


pytestmark = pytest.mark.unit


def test_given_windows_x86_64_when_reading_catalog_then_includes_vendors(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Windows")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "AMD64")

	catalog = catalog_mod.platform_catalog()

	assert catalog["uv"].kind == "zip"
	assert catalog["uv"].url.endswith(".zip")
	assert catalog["tesseract"].kind == "nsis_installer"
	assert catalog["7zr"].kind == "binary"
	assert catalog["7zip"].kind == "sfx"
	assert catalog["ffmpeg"].kind == "zip"
	assert "win64" in catalog["ffmpeg"].url
	assert catalog_mod.vendor_downloads_supported() is True


def test_given_windows_nsis_tesseract_when_installing_then_extracts_without_running_setup(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Windows")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "AMD64")
	monkeypatch.setattr(vendor_mod.platform, "system", lambda: "Windows")

	from srxy.adapters.inbound.installer.tessdata_langs import tessdata_url

	setup_bytes = b"fake-tesseract-nsis-setup"
	sevenzr_bytes = b"fake-7zr"
	sevenzip_bytes = b"fake-7zip-sfx"
	downloads = {
		catalog_mod.WIN_X86_64_CATALOG["tesseract"].url: setup_bytes,
		catalog_mod.WIN_X86_64_CATALOG["7zr"].url: sevenzr_bytes,
		catalog_mod.WIN_X86_64_CATALOG["7zip"].url: sevenzip_bytes,
		tessdata_url("eng"): b"fake-eng",
		tessdata_url("osd"): b"fake-osd",
	}
	run_cmds: list[list[str]] = []

	def fake_download_to_temp(
		url: str,
		*,
		suffix: str,
		sha256: str = "",
		label: str = "",
		progress: object | None = None,
		headers: dict[str, str] | None = None,
		require_digest: bool = True,
	):
		_ = sha256, label, progress, headers, require_digest
		dest = tmp_path / f"dl-{hashlib.sha256(url.encode()).hexdigest()[:12]}{suffix}"
		dest.write_bytes(downloads[url])
		return dest

	def fake_download_file(
		url: str,
		dest: Path,
		*,
		sha256: str = "",
		label: str = "",
		progress: object | None = None,
		headers: dict[str, str] | None = None,
		require_digest: bool = True,
	):
		_ = sha256, label, progress, headers, require_digest
		dest.parent.mkdir(parents=True, exist_ok=True)
		dest.write_bytes(downloads[url])

	def fake_run(cmd: list[str], **kwargs: object):
		_ = kwargs
		run_cmds.append([str(part) for part in cmd])
		exe = Path(cmd[0])
		if exe.name.lower() == "7zr.exe" or exe.read_bytes() == sevenzr_bytes:
			# 7zr x <sfx> -o<tools> -y
			out_flag = next(part for part in cmd if part.startswith("-o"))
			tools = Path(out_flag[2:])
			tools.mkdir(parents=True, exist_ok=True)
			(tools / "7z.exe").write_bytes(b"fake-7z")
			(tools / "7z.dll").write_bytes(b"fake-7z-dll")
			return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
		if exe.name.lower() == "7z.exe" or exe.read_bytes() == b"fake-7z":
			out_flag = next(part for part in cmd if part.startswith("-o"))
			extract_root = Path(out_flag[2:])
			extract_root.mkdir(parents=True, exist_ok=True)
			(extract_root / "$PLUGINSDIR").mkdir(exist_ok=True)
			(extract_root / "$PLUGINSDIR" / "ignore.bin").write_bytes(b"x")
			(extract_root / "tesseract.exe").write_bytes(b"fake-tesseract-exe")
			(extract_root / "libtesseract-5.dll").write_bytes(b"fake-dll")
			(extract_root / "tessdata").mkdir(exist_ok=True)
			(extract_root / "tessdata" / "eng.traineddata").write_bytes(b"fake-eng")
			archive = Path(cmd[2])
			assert archive.read_bytes() == setup_bytes
			assert archive.name.endswith(".exe")
			return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
		raise AssertionError(f"unexpected subprocess command: {cmd}")

	monkeypatch.setattr(vendor_mod, "download_to_temp", fake_download_to_temp)
	monkeypatch.setattr(vendor_mod, "download_file", fake_download_file)
	monkeypatch.setattr(vendor_mod.subprocess, "run", fake_run)
	monkeypatch.setattr(vendor_mod, "_self_check_tesseract", lambda *_a, **_k: None)
	from srxy.adapters.inbound.installer.resolve import ResolvedArtifact

	item = catalog_mod.WIN_X86_64_CATALOG["tesseract"]
	monkeypatch.setattr(
		vendor_mod,
		"resolve_tesseract",
		lambda: ResolvedArtifact(
			name=item.name,
			version=item.version,
			url=item.url,
			sha256=item.sha256,
			kind=item.kind,
		),
	)

	prefix = tmp_path / "prefix"
	binary = vendor_mod.install_tesseract(prefix)

	assert binary.is_file()
	assert binary.read_bytes() == b"fake-tesseract-exe"
	assert binary.parent.name == "bin"
	assert (prefix / "vendor" / "tesseract" / "bin" / "libtesseract-5.dll").is_file()
	assert (prefix / "vendor" / "tesseract" / "tessdata" / "eng.traineddata").is_file()
	assert (prefix / "vendor" / "tesseract" / "tessdata" / "osd.traineddata").is_file()
	assert not (prefix / "vendor" / "tesseract" / "_work").exists()
	# Setup EXE must never be the process image (CreateProcess elevation / WinError 740).
	assert all(Path(cmd[0]).read_bytes() != setup_bytes for cmd in run_cmds if Path(cmd[0]).is_file())
	assert all(not cmd[0].lower().endswith("tesseract-setup.exe") for cmd in run_cmds)


def test_given_darwin_arm64_when_reading_catalog_then_includes_ffmpeg_and_tesseract(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "arm64")

	catalog = catalog_mod.platform_catalog()

	assert "uv" in catalog
	assert catalog["ffmpeg"].kind == "zip"
	assert catalog["tesseract"].kind == "brew_bottles"
	assert catalog["ffmpeg"].sha256
	assert catalog["tesseract"].sha256
	assert catalog["tesseract"].url.startswith("https://ghcr.io/v2/homebrew/core/")
	assert "illescasDaniel/srxy" not in catalog["tesseract"].url
	assert catalog_mod.vendor_downloads_supported() is True


def test_given_darwin_arm64_tesseract_bottles_when_listed_then_are_pinned_ghcr_blobs():
	bottles = catalog_mod.DARWIN_ARM64_TESSERACT_BOTTLES
	assert bottles
	assert bottles[0].formula == "tesseract"
	formulas = {bottle.formula for bottle in bottles}
	assert {"tesseract", "leptonica", "libarchive", "webp"}.issubset(formulas)
	for bottle in bottles:
		assert bottle.url == (f"https://ghcr.io/v2/homebrew/core/{bottle.formula}/blobs/sha256:{bottle.sha256}")
		assert len(bottle.sha256) == 64
		assert "illescasDaniel/srxy" not in bottle.url


def test_given_darwin_x86_64_when_reading_catalog_then_vendors_tesseract_and_ffmpeg(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "x86_64")

	catalog = catalog_mod.platform_catalog()

	assert "uv" in catalog
	assert catalog["ffmpeg"].kind == "zip"
	assert catalog["tesseract"].kind == "brew_bottles"
	assert catalog_mod.vendor_downloads_supported() is True


def test_given_darwin_arm64e_when_reading_catalog_then_normalizes_to_arm64(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "arm64e")

	catalog = catalog_mod.platform_catalog()

	assert "uv" in catalog
	assert catalog["uv"].url.endswith("uv-aarch64-apple-darwin.tar.gz")
	assert catalog_mod.vendor_downloads_supported() is True


def test_given_tesseract_brew_bottles_when_installing_then_assembles_relocatable_tree(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "arm64")
	monkeypatch.setattr(vendor_mod.platform, "system", lambda: "Darwin")

	bottle_root = tmp_path / "bottle-src"
	(bottle_root / "tesseract" / "5.5.3" / "bin").mkdir(parents=True)
	(bottle_root / "tesseract" / "5.5.3" / "lib").mkdir(parents=True)
	(bottle_root / "tesseract" / "5.5.3" / "share" / "tessdata").mkdir(parents=True)
	(bottle_root / "leptonica" / "1.87.0" / "lib").mkdir(parents=True)
	bin_src = bottle_root / "tesseract" / "5.5.3" / "bin" / "tesseract"
	lib_tess = bottle_root / "tesseract" / "5.5.3" / "lib" / "libtesseract.5.dylib"
	lib_lept = bottle_root / "leptonica" / "1.87.0" / "lib" / "libleptonica.6.dylib"
	eng_src = bottle_root / "tesseract" / "5.5.3" / "share" / "tessdata" / "eng.traineddata"
	bin_src.write_bytes(b"fake-tesseract")
	lib_tess.write_bytes(b"fake-libtesseract")
	lib_lept.write_bytes(b"fake-libleptonica")
	eng_src.write_bytes(b"fake-eng")

	archives: dict[str, Path] = {}
	for bottle in catalog_mod.DARWIN_ARM64_TESSERACT_BOTTLES:
		archive = tmp_path / f"{bottle.formula}.tar.gz"
		with tarfile.open(archive, "w:gz") as handle:
			# Only first two bottles need payload for this unit test; others stay empty-ish.
			if bottle.formula == "tesseract":
				for path in bottle_root.joinpath("tesseract").rglob("*"):
					if path.is_file():
						handle.add(path, arcname=str(path.relative_to(bottle_root)))
			elif bottle.formula == "leptonica":
				for path in bottle_root.joinpath("leptonica").rglob("*"):
					if path.is_file():
						handle.add(path, arcname=str(path.relative_to(bottle_root)))
			else:
				handle.addfile(tarfile.TarInfo(name=f"{bottle.formula}/.keep"))
		archives[bottle.url] = archive

	def fake_download_to_temp(
		url: str,
		*,
		suffix: str,
		sha256: str = "",
		label: str = "",
		progress: object | None = None,
		headers: dict[str, str] | None = None,
		require_digest: bool = True,
	):
		_ = suffix, sha256, label, progress, require_digest
		assert headers == catalog_mod.GHCR_BOTTLE_HEADERS
		src = archives[url]
		dest = tmp_path / f"dl-{src.name}"
		dest.write_bytes(src.read_bytes())
		return dest

	deps = {
		str(bin_src.resolve()): [
			"@@HOMEBREW_CELLAR@@/tesseract/5.5.3/lib/libtesseract.5.dylib",
			"@@HOMEBREW_PREFIX@@/opt/leptonica/lib/libleptonica.6.dylib",
			"/usr/lib/libSystem.B.dylib",
		],
		str(lib_tess.resolve()): [
			"@@HOMEBREW_CELLAR@@/tesseract/5.5.3/lib/libtesseract.5.dylib",
			"@@HOMEBREW_PREFIX@@/opt/leptonica/lib/libleptonica.6.dylib",
			"/usr/lib/libSystem.B.dylib",
		],
		str(lib_lept.resolve()): [
			"@@HOMEBREW_PREFIX@@/opt/leptonica/lib/libleptonica.6.dylib",
			"/usr/lib/libSystem.B.dylib",
		],
	}

	def fake_otool_deps(path: Path) -> list[str]:
		# After copy, match by file basename content key via bytes identity in copied tree.
		data = path.read_bytes()
		if data == b"fake-tesseract":
			return deps[str(bin_src.resolve())]
		if data == b"fake-libtesseract":
			return deps[str(lib_tess.resolve())]
		if data == b"fake-libleptonica":
			return deps[str(lib_lept.resolve())]
		return ["/usr/lib/libSystem.B.dylib"]

	monkeypatch.setattr(vendor_mod, "download_to_temp", fake_download_to_temp)
	monkeypatch.setattr(vendor_mod, "_otool_deps", fake_otool_deps)
	monkeypatch.setattr(vendor_mod, "_run_install_name_tool", lambda *_args: None)
	monkeypatch.setattr(vendor_mod, "_adhoc_codesign", lambda _path: None)
	monkeypatch.setattr(vendor_mod, "_self_check_tesseract", lambda *_args, **_kwargs: None)
	monkeypatch.setattr(
		vendor_mod,
		"resolve_tesseract_brew_bottles",
		lambda **_kwargs: catalog_mod.DARWIN_ARM64_TESSERACT_BOTTLES,
	)

	from srxy.adapters.inbound.installer.tessdata_langs import tessdata_url

	def fake_download_file(
		url: str,
		dest: Path,
		*,
		sha256: str = "",
		label: str = "",
		progress: object | None = None,
		headers: dict[str, str] | None = None,
		require_digest: bool = True,
	):
		_ = sha256, label, progress, headers, require_digest
		if url == tessdata_url("osd"):
			dest.write_bytes(b"fake-osd")
			return
		raise AssertionError(f"unexpected download_file url: {url}")

	monkeypatch.setattr(vendor_mod, "download_file", fake_download_file)

	prefix = tmp_path / "prefix"
	binary = vendor_mod.install_tesseract(prefix)

	assert binary.is_file()
	assert binary.read_bytes() == b"fake-tesseract"
	assert (prefix / "vendor" / "tesseract" / "lib" / "libtesseract.5.dylib").is_file()
	assert (prefix / "vendor" / "tesseract" / "lib" / "libleptonica.6.dylib").is_file()
	assert (prefix / "vendor" / "tesseract" / "tessdata" / "eng.traineddata").read_bytes() == b"fake-eng"
	assert (prefix / "vendor" / "tesseract" / "tessdata" / "osd.traineddata").read_bytes() == b"fake-osd"
	assert not (prefix / "vendor" / "tesseract" / "_bottles").exists()


def test_given_ffmpeg_zip_when_installing_then_places_binary(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "arm64")
	monkeypatch.setattr(vendor_mod.platform, "system", lambda: "Darwin")

	item = catalog_mod.DARWIN_ARM64_CATALOG["ffmpeg"]
	payload = b"#!/bin/sh\necho fake-ffmpeg\n"
	zip_path = tmp_path / "ffmpeg.zip"
	with zipfile.ZipFile(zip_path, "w") as handle:
		handle.writestr("ffmpeg", payload)

	digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
	from srxy.adapters.inbound.installer.resolve import ResolvedArtifact

	monkeypatch.setattr(
		vendor_mod,
		"resolve_ffmpeg",
		lambda: ResolvedArtifact(
			name="ffmpeg",
			version=item.version,
			url="https://example.invalid/ffmpeg.zip",
			sha256=digest,
			kind="zip",
		),
	)

	def fake_download_to_temp(
		url: str,
		*,
		suffix: str,
		sha256: str = "",
		label: str = "",
		progress: object | None = None,
		headers: dict[str, str] | None = None,
		require_digest: bool = True,
	):
		_ = url, suffix, sha256, label, progress, headers, require_digest
		dest = tmp_path / "downloaded.zip"
		dest.write_bytes(zip_path.read_bytes())
		return dest

	monkeypatch.setattr(vendor_mod, "download_to_temp", fake_download_to_temp)
	monkeypatch.setattr(vendor_mod, "_adhoc_codesign", lambda _path: None)

	prefix = tmp_path / "prefix"
	binary = vendor_mod.install_ffmpeg(prefix)

	assert binary.is_file()
	assert binary.read_bytes() == payload
	# Executable bit is meaningful on Unix only (and this test monkeypatches platform.system).
	if sys.platform != "win32":
		assert binary.stat().st_mode & 0o111


def test_given_windows_when_exposing_ffmpeg_then_copies_instead_of_symlink(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	monkeypatch.setattr(vendor_mod.platform, "system", lambda: "Windows")
	vendor = tmp_path / "vendor" / "ffmpeg"
	real = vendor / "extracted" / "ffmpeg.exe"
	real.parent.mkdir(parents=True)
	real.write_bytes(b"MZ-fake")

	target = vendor_mod._expose_ffmpeg_bin(vendor, real)  # pyright: ignore[reportPrivateUsage]

	assert target == vendor / "bin" / "ffmpeg.exe"
	assert target.is_file()
	assert not target.is_symlink()
	assert target.read_bytes() == b"MZ-fake"


def test_given_unix_when_exposing_ffmpeg_then_symlinks(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	monkeypatch.setattr(vendor_mod.platform, "system", lambda: "Linux")
	vendor = tmp_path / "vendor" / "ffmpeg"
	real = vendor / "extracted" / "ffmpeg"
	real.parent.mkdir(parents=True)
	real.write_bytes(b"#!/bin/sh\n")

	try:
		probe = tmp_path / "symlink-probe"
		probe.symlink_to(real)
		probe.unlink()
	except OSError:
		pytest.skip("symlinks are not available on this platform")

	target = vendor_mod._expose_ffmpeg_bin(vendor, real)  # pyright: ignore[reportPrivateUsage]

	assert target == vendor / "bin" / "ffmpeg"
	assert target.is_symlink()
	assert target.resolve() == real.resolve()


def test_given_symlink_fails_when_exposing_ffmpeg_then_copies(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	monkeypatch.setattr(vendor_mod.platform, "system", lambda: "Linux")

	def boom(_src: Path, _dst: Path):
		raise OSError("no symlink")

	monkeypatch.setattr(vendor_mod.os, "symlink", boom)
	vendor = tmp_path / "vendor" / "ffmpeg"
	real = vendor / "extracted" / "ffmpeg"
	real.parent.mkdir(parents=True)
	real.write_bytes(b"payload")

	target = vendor_mod._expose_ffmpeg_bin(vendor, real)  # pyright: ignore[reportPrivateUsage]

	assert target.is_file()
	assert not target.is_symlink()
	assert target.read_bytes() == b"payload"


def test_given_existing_bin_entry_when_exposing_ffmpeg_then_replaces(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	monkeypatch.setattr(vendor_mod.platform, "system", lambda: "Windows")
	vendor = tmp_path / "vendor" / "ffmpeg"
	bin_dir = vendor / "bin"
	bin_dir.mkdir(parents=True)
	stale = bin_dir / "ffmpeg.exe"
	stale.write_bytes(b"old")
	real = vendor / "extracted" / "ffmpeg.exe"
	real.parent.mkdir(parents=True)
	real.write_bytes(b"new")

	target = vendor_mod._expose_ffmpeg_bin(vendor, real)  # pyright: ignore[reportPrivateUsage]

	assert target.read_bytes() == b"new"
