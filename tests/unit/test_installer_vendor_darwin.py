"""Unit tests for installer vendor catalog and Darwin brew-bottle install."""

from __future__ import annotations

import hashlib
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from srxy.adapters.inbound.installer import catalog as catalog_mod, vendor as vendor_mod


def test_given_windows_x86_64_when_reading_catalog_then_includes_vendors(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Windows")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "AMD64")

	catalog = catalog_mod.platform_catalog()

	assert catalog["uv"].kind == "zip"
	assert catalog["uv"].url.endswith(".zip")
	assert catalog["tesseract"].kind == "inno_installer"
	assert catalog["ffmpeg"].kind == "zip"
	assert "win64" in catalog["ffmpeg"].url
	assert catalog_mod.vendor_downloads_supported() is True


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


def test_given_darwin_x86_64_when_reading_catalog_then_only_uv_is_pinned(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(catalog_mod.platform, "system", lambda: "Darwin")
	monkeypatch.setattr(catalog_mod.platform, "machine", lambda: "x86_64")

	catalog = catalog_mod.platform_catalog()

	assert set(catalog.keys()) == {"uv"}
	assert catalog["uv"].url.endswith("uv-x86_64-apple-darwin.tar.gz")
	assert catalog_mod.vendor_downloads_supported() is False


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
	):
		_ = suffix, sha256, label, progress
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

	prefix = tmp_path / "prefix"
	binary = vendor_mod.install_tesseract(prefix)

	assert binary.is_file()
	assert binary.read_bytes() == b"fake-tesseract"
	assert (prefix / "vendor" / "tesseract" / "lib" / "libtesseract.5.dylib").is_file()
	assert (prefix / "vendor" / "tesseract" / "lib" / "libleptonica.6.dylib").is_file()
	assert (prefix / "vendor" / "tesseract" / "tessdata" / "eng.traineddata").read_bytes() == b"fake-eng"
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

	def fake_artifact(name: str):
		if name == "ffmpeg":
			return catalog_mod.DownloadArtifact(
				name="ffmpeg",
				version=item.version,
				url="https://example.invalid/ffmpeg.zip",
				sha256=digest,
				kind="zip",
			)
		return catalog_mod.DARWIN_ARM64_CATALOG[name]

	monkeypatch.setattr(vendor_mod, "artifact", fake_artifact)

	def fake_download_to_temp(
		url: str,
		*,
		suffix: str,
		sha256: str = "",
		label: str = "",
		progress: object | None = None,
		headers: dict[str, str] | None = None,
	):
		_ = url, suffix, sha256, label, progress, headers
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
