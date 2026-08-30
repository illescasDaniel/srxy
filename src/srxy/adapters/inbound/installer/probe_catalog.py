"""Probe installer catalog / resolved vendor URLs without full downloads."""

from __future__ import annotations

import sys

from srxy.adapters.inbound.installer.catalog import (
	DARWIN_ARM64_CATALOG,
	DARWIN_ARM64_TESSERACT_BOTTLES,
	DARWIN_X86_64_CATALOG,
	GHCR_BOTTLE_HEADERS,
	LINUX_X86_64_CATALOG,
	WIN_X86_64_CATALOG,
)
from srxy.adapters.inbound.installer.download import probe_url
from srxy.adapters.inbound.installer.resolve import (
	resolve_ffmpeg_btbn,
	resolve_ffmpeg_martin_riedl,
	resolve_tesseract_brew_bottles,
	resolve_tesseract_linux,
	resolve_tesseract_windows,
)


def _probe_catalog_maps() -> list[tuple[str, str, dict[str, str] | None]]:
	targets: list[tuple[str, str, dict[str, str] | None]] = []
	# Only probe static pins that are still the install source of truth.
	# ffmpeg/tesseract are resolved at install time (and probed via resolvers).
	static_ok = {"uv", "7zr", "7zip"}
	for label, catalog in (
		("linux", LINUX_X86_64_CATALOG),
		("win", WIN_X86_64_CATALOG),
		("darwin-arm64", DARWIN_ARM64_CATALOG),
		("darwin-x86_64", DARWIN_X86_64_CATALOG),
	):
		for name, item in catalog.items():
			if name not in static_ok:
				continue
			if not item.sha256:
				continue
			targets.append((f"catalog:{label}/{name}", item.url, None))
	for bottle in DARWIN_ARM64_TESSERACT_BOTTLES:
		targets.append((f"catalog:brew/{bottle.formula}", bottle.url, dict(GHCR_BOTTLE_HEADERS)))
	return targets


def _probe_resolvers() -> list[tuple[str, str, dict[str, str] | None]]:
	targets: list[tuple[str, str, dict[str, str] | None]] = []
	ffmpeg_linux = resolve_ffmpeg_btbn(system="linux", machine="x86_64")
	targets.append(("resolve:ffmpeg/linux", ffmpeg_linux.url, None))
	ffmpeg_win = resolve_ffmpeg_btbn(system="windows", machine="x86_64")
	targets.append(("resolve:ffmpeg/windows", ffmpeg_win.url, None))
	ffmpeg_arm = resolve_ffmpeg_martin_riedl(arch="arm64")
	targets.append(("resolve:ffmpeg/darwin-arm64", ffmpeg_arm.url, None))
	ffmpeg_amd = resolve_ffmpeg_martin_riedl(arch="amd64")
	targets.append(("resolve:ffmpeg/darwin-amd64", ffmpeg_amd.url, None))

	tess_linux = resolve_tesseract_linux()
	targets.append(("resolve:tesseract/linux", tess_linux.url, None))
	tess_win = resolve_tesseract_windows()
	targets.append(("resolve:tesseract/windows", tess_win.url, None))

	for machine, label in (("arm64", "darwin-arm64"), ("x86_64", "darwin-x86_64")):
		bottles = resolve_tesseract_brew_bottles(machine=machine)
		primary = bottles[0]
		targets.append((f"resolve:tesseract/{label}", primary.url, dict(GHCR_BOTTLE_HEADERS)))
	return targets


def main(argv: list[str] | None = None) -> int:
	_ = argv
	failures: list[str] = []
	seen: set[str] = set()
	for label, url, headers in _probe_catalog_maps() + _probe_resolvers():
		if url in seen:
			print(f"OK  {label} (duplicate url skipped)")
			continue
		seen.add(url)
		try:
			final = probe_url(url, headers=headers)
			print(f"OK  {label}\n    {final}")
		except RuntimeError as exc:
			print(f"FAIL {label}: {exc}", file=sys.stderr)
			failures.append(label)
	if failures:
		print(f"{len(failures)} probe(s) failed", file=sys.stderr)
		return 1
	print("all catalog/resolver probes OK")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
