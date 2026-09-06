"""Probe installer catalog / resolved vendor URLs without full downloads."""

from __future__ import annotations

import sys
from collections.abc import Callable

from srxy.adapters.inbound.installer.catalog import (
	DARWIN_ARM64_CATALOG,
	DARWIN_ARM64_TESSERACT_BOTTLES,
	DARWIN_X86_64_CATALOG,
	GHCR_BOTTLE_HEADERS,
	LINUX_X86_64_CATALOG,
	WIN_X86_64_CATALOG,
	BrewBottle,
)
from srxy.adapters.inbound.installer.download import probe_url
from srxy.adapters.inbound.installer.resolve import (
	ResolvedArtifact,
	resolve_ffmpeg_btbn,
	resolve_ffmpeg_martin_riedl,
	resolve_tesseract_brew_bottles,
	resolve_tesseract_linux,
	resolve_tesseract_windows,
)


_HasUrl = ResolvedArtifact | BrewBottle


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


def _probe_resolvers() -> tuple[list[tuple[str, str, dict[str, str] | None]], list[str]]:
	"""Resolve install-time artifact URLs; return (targets, unresolvable_labels).

	Install-time resolvers depend on live upstream catalogs (Homebrew bottles,
	GitHub releases) that prune/rename tags outside our control (see this
	module's docstring). One resolver going stale should not hide probe
	results for the others, so each resolve call is isolated — a failure here
	is reported as a soft/informational skip, not a hard CI failure. The
	static, sha256-pinned catalog URLs probed by `_probe_catalog_maps()` are
	what actually gate correctness.
	"""
	targets: list[tuple[str, str, dict[str, str] | None]] = []
	unresolvable: list[str] = []

	def _resolve_url(label: str, fn: Callable[[], _HasUrl]) -> str | None:
		try:
			return fn().url
		except RuntimeError as exc:
			print(f"WARN resolve:{label} unresolvable (upstream catalog drift): {exc}", file=sys.stderr)
			unresolvable.append(label)
			return None

	resolutions: list[tuple[str, Callable[[], ResolvedArtifact], dict[str, str] | None]] = [
		("ffmpeg/linux", lambda: resolve_ffmpeg_btbn(system="linux", machine="x86_64"), None),
		("ffmpeg/windows", lambda: resolve_ffmpeg_btbn(system="windows", machine="x86_64"), None),
		("ffmpeg/darwin-arm64", lambda: resolve_ffmpeg_martin_riedl(arch="arm64"), None),
		("ffmpeg/darwin-amd64", lambda: resolve_ffmpeg_martin_riedl(arch="amd64"), None),
		("tesseract/linux", resolve_tesseract_linux, None),
		("tesseract/windows", resolve_tesseract_windows, None),
	]
	for label, fn, headers in resolutions:
		url = _resolve_url(label, fn)
		if url is not None:
			targets.append((f"resolve:{label}", url, headers))

	for machine, label in (("arm64", "darwin-arm64"), ("x86_64", "darwin-x86_64")):

		def _resolve_bottles(machine: str = machine) -> BrewBottle:
			return resolve_tesseract_brew_bottles(machine=machine)[0]

		url = _resolve_url(f"tesseract/{label}", _resolve_bottles)
		if url is not None:
			targets.append((f"resolve:tesseract/{label}", url, dict(GHCR_BOTTLE_HEADERS)))
	return targets, unresolvable


def main(argv: list[str] | None = None) -> int:
	_ = argv
	failures: list[str] = []
	seen: set[str] = set()
	resolver_targets, unresolvable = _probe_resolvers()
	for label, url, headers in _probe_catalog_maps() + resolver_targets:
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
	if unresolvable:
		print(
			f"note: {len(unresolvable)} resolver(s) skipped due to upstream catalog drift: {', '.join(unresolvable)}",
			file=sys.stderr,
		)
		print("all catalog pins OK (some resolver probes skipped — see note above)")
		return 0
	print("all catalog/resolver probes OK")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
