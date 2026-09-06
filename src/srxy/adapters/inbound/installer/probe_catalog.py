"""Probe installer catalog / resolved vendor URLs without full downloads."""

from __future__ import annotations

import sys
import time
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


_ResolvedTarget = ResolvedArtifact | BrewBottle


# This probe hits third-party APIs (GitHub releases, Homebrew, martin-riedl) purely
# as an advisory health check — it is not part of the code quality gate. Upstream
# hosts occasionally return transient 5xx/timeouts under load; retry generously here
# (independent of resolve.py's own conservative install-time retry budget) so a
# short blip does not flag a probe failure.
_RESOLVE_RETRIES = 3
_RESOLVE_RETRY_BACKOFF_SECONDS = 3.0


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


def _resolver_targets() -> list[tuple[str, Callable[[], _ResolvedTarget], dict[str, str] | None]]:
	"""Lazy (label, resolver, probe_headers) triples — each resolved independently so
	one upstream API hiccup (e.g. GitHub releases for BtbN) does not abort probing the
	rest (Homebrew, UB-Mannheim, DanielMYT, ... are unrelated hosts/APIs)."""
	return [
		("resolve:ffmpeg/linux", lambda: resolve_ffmpeg_btbn(system="linux", machine="x86_64"), None),
		("resolve:ffmpeg/windows", lambda: resolve_ffmpeg_btbn(system="windows", machine="x86_64"), None),
		("resolve:ffmpeg/darwin-arm64", lambda: resolve_ffmpeg_martin_riedl(arch="arm64"), None),
		("resolve:ffmpeg/darwin-amd64", lambda: resolve_ffmpeg_martin_riedl(arch="amd64"), None),
		("resolve:tesseract/linux", resolve_tesseract_linux, None),
		("resolve:tesseract/windows", resolve_tesseract_windows, None),
		(
			"resolve:tesseract/darwin-arm64",
			lambda: resolve_tesseract_brew_bottles(machine="arm64")[0],
			dict(GHCR_BOTTLE_HEADERS),
		),
		(
			"resolve:tesseract/darwin-x86_64",
			lambda: resolve_tesseract_brew_bottles(machine="x86_64")[0],
			dict(GHCR_BOTTLE_HEADERS),
		),
	]


def _resolve_with_retries(resolver: Callable[[], _ResolvedTarget], *, label: str) -> _ResolvedTarget:
	last: Exception = RuntimeError(f"{label}: resolver never attempted")
	for attempt in range(_RESOLVE_RETRIES):
		try:
			return resolver()
		except Exception as exc:  # noqa: BLE001 — advisory probe: report and retry any resolver failure
			last = exc
			if attempt + 1 >= _RESOLVE_RETRIES:
				break
			print(
				f"WARN {label}: resolve attempt {attempt + 1}/{_RESOLVE_RETRIES} failed ({exc}); retrying...",
				file=sys.stderr,
			)
			time.sleep(_RESOLVE_RETRY_BACKOFF_SECONDS * (attempt + 1))
	raise last


def main(argv: list[str] | None = None) -> int:
	_ = argv
	failures: list[str] = []
	seen: set[str] = set()

	for label, url, headers in _probe_catalog_maps():
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

	for label, resolver, probe_headers in _resolver_targets():
		try:
			resolved = _resolve_with_retries(resolver, label=label)
		except Exception as exc:  # noqa: BLE001 — advisory probe: never let one target crash the run
			print(f"FAIL {label}: could not resolve: {exc}", file=sys.stderr)
			failures.append(label)
			continue
		if resolved.url in seen:
			print(f"OK  {label} (duplicate url skipped)")
			continue
		seen.add(resolved.url)
		try:
			final = probe_url(resolved.url, headers=probe_headers)
			print(f"OK  {label}\n    {final}")
		except RuntimeError as exc:
			print(f"FAIL {label}: {exc}", file=sys.stderr)
			failures.append(label)

	if failures:
		print(f"{len(failures)} probe(s) failed: {', '.join(failures)}", file=sys.stderr)
		return 1
	print("all catalog/resolver probes OK")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
