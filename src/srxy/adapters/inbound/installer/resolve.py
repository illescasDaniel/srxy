"""Resolve latest upstream FFmpeg / Tesseract artifacts at install time.

Static catalog pins remain as fallback. Upstream hosts (especially BtbN) prune
old release tags, so install-time resolution keeps vendor downloads working.
"""

from __future__ import annotations

import json
import platform
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from srxy.adapters.inbound.installer.catalog import (
	BrewBottle,
	DARWIN_ARM64_TESSERACT_BOTTLES,
	DownloadArtifact,
	_brew_bottle,
	_normalize_machine,
	artifact,
)


_USER_AGENT = "srxy-installer"
_API_TIMEOUT = 45.0

_BTBN_RELEASES = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases?per_page=15"
_TESSERACT_STATIC_RELEASES = "https://api.github.com/repos/DanielMYT/tesseract-static/releases?per_page=10"
_UB_MANNHEIM_RELEASES = "https://api.github.com/repos/UB-Mannheim/tesseract/releases?per_page=10"
_BREW_FORMULA = "https://formulae.brew.sh/api/formula/{formula}.json"
_MARTIN_RIEDL_LATEST = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/ffmpeg.zip"

# Same dependency set as DARWIN_ARM64_TESSERACT_BOTTLES; digests refreshed via brew API.
_DARWIN_TESSERACT_FORMULAS: tuple[str, ...] = tuple(b.formula for b in DARWIN_ARM64_TESSERACT_BOTTLES)

_WIN64_LGPL = re.compile(r"^ffmpeg-n[\w.-]+-win64-lgpl-shared-[\d.]+\.zip$")
_LINUX64_LGPL = re.compile(r"^ffmpeg-n[\w.-]+-linux64-lgpl-shared-[\d.]+\.tar\.xz$")
_W64_SETUP = re.compile(r"^tesseract-ocr-w64-setup-.+\.exe$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ResolvedArtifact:
	name: str
	version: str
	url: str
	sha256: str
	kind: str
	notes: str = ""


def _http_json(url: str) -> Any:
	if not url.startswith("https://"):
		raise RuntimeError(f"refusing non-https URL: {url}")
	request = urllib.request.Request(  # noqa: S310
		url,
		headers={
			"User-Agent": _USER_AGENT,
			"Accept": "application/vnd.github+json, application/json",
		},
	)
	try:
		with urllib.request.urlopen(request, timeout=_API_TIMEOUT) as response:  # noqa: S310
			return json.loads(response.read().decode("utf-8"))
	except urllib.error.URLError as exc:
		raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def _follow_redirect_url(url: str) -> str:
	"""Follow redirects with a ranged GET; return the final HTTPS URL."""
	if not url.startswith("https://"):
		raise RuntimeError(f"refusing non-https URL: {url}")
	request = urllib.request.Request(  # noqa: S310
		url,
		headers={"User-Agent": _USER_AGENT, "Range": "bytes=0-0"},
	)
	try:
		with urllib.request.urlopen(request, timeout=_API_TIMEOUT) as response:  # noqa: S310
			response.read(1)
			final = response.geturl()
	except urllib.error.URLError as exc:
		raise RuntimeError(f"failed to resolve redirect for {url}: {exc}") from exc
	if not final.startswith("https://"):
		raise RuntimeError(f"redirect landed on non-https URL: {final}")
	return final


def _host() -> tuple[str, str]:
	return platform.system().lower(), _normalize_machine(platform.machine())


def _pick_btbn_asset(assets: list[dict[str, Any]], *, pattern: re.Pattern[str]) -> dict[str, Any] | None:
	matches = [a for a in assets if pattern.match(str(a.get("name") or ""))]
	if not matches:
		return None
	# Prefer release-line (ffmpeg-n…) — already filtered — stable sort by name.
	matches.sort(key=lambda a: str(a.get("name") or ""), reverse=True)
	return matches[0]


def resolve_ffmpeg_btbn(*, system: str, machine: str) -> ResolvedArtifact:
	if machine != "x86_64":
		raise RuntimeError(f"BtbN ffmpeg resolve unsupported for {system}/{machine}")
	if system == "windows":
		pattern = _WIN64_LGPL
		kind = "zip"
	elif system == "linux":
		pattern = _LINUX64_LGPL
		kind = "archive"
	else:
		raise RuntimeError(f"BtbN ffmpeg resolve unsupported for {system}/{machine}")

	releases = _http_json(_BTBN_RELEASES)
	if not isinstance(releases, list):
		raise RuntimeError("unexpected GitHub releases payload for BtbN/FFmpeg-Builds")

	for release in releases:
		if not isinstance(release, dict):
			continue
		if release.get("draft"):
			continue
		tag = str(release.get("tag_name") or "")
		if not tag.startswith("autobuild-"):
			continue
		assets = release.get("assets") or []
		if not isinstance(assets, list):
			continue
		picked = _pick_btbn_asset(assets, pattern=pattern)
		if picked is None:
			continue
		url = str(picked.get("browser_download_url") or "")
		name = str(picked.get("name") or "")
		if not url.startswith("https://"):
			continue
		version = name.removesuffix(".zip").removesuffix(".tar.xz")
		return ResolvedArtifact(
			name="ffmpeg",
			version=version,
			url=url,
			sha256="",
			kind=kind,
			notes=f"BtbN {tag} LGPL shared (resolved at install time).",
		)
	raise RuntimeError("no suitable BtbN autobuild LGPL shared ffmpeg asset found")


def resolve_ffmpeg_martin_riedl(*, arch: str) -> ResolvedArtifact:
	if arch not in {"arm64", "amd64"}:
		raise RuntimeError(f"martin-riedl arch unsupported: {arch}")
	redirect = _MARTIN_RIEDL_LATEST.format(arch=arch)
	final = _follow_redirect_url(redirect)
	# …/download/macos/arm64/<id>_<ver>/ffmpeg.zip
	version = "latest"
	parts = final.rstrip("/").split("/")
	if len(parts) >= 2 and parts[-1] == "ffmpeg.zip":
		stamp = parts[-2]
		if "_" in stamp:
			version = stamp.split("_", 1)[1]
	return ResolvedArtifact(
		name="ffmpeg",
		version=version,
		url=final,
		sha256="",
		kind="zip",
		notes=f"martin-riedl macOS {arch} release build (resolved at install time).",
	)


def resolve_ffmpeg() -> ResolvedArtifact:
	system, machine = _host()
	try:
		if system in {"linux", "windows"} and machine == "x86_64":
			return resolve_ffmpeg_btbn(system=system, machine=machine)
		if system == "darwin" and machine == "arm64":
			return resolve_ffmpeg_martin_riedl(arch="arm64")
		if system == "darwin" and machine == "x86_64":
			return resolve_ffmpeg_martin_riedl(arch="amd64")
		raise RuntimeError(f"ffmpeg resolve unsupported on {system}/{machine}")
	except RuntimeError:
		# Fall back to the static catalog pin when present.
		try:
			item = artifact("ffmpeg")
		except KeyError:
			raise
		return ResolvedArtifact(
			name=item.name,
			version=item.version,
			url=item.url,
			sha256=item.sha256,
			kind=item.kind,
			notes=item.notes or "catalog fallback",
		)


def resolve_tesseract_linux() -> ResolvedArtifact:
	releases = _http_json(_TESSERACT_STATIC_RELEASES)
	if not isinstance(releases, list):
		raise RuntimeError("unexpected GitHub releases payload for DanielMYT/tesseract-static")
	for release in releases:
		if not isinstance(release, dict) or release.get("draft"):
			continue
		tag = str(release.get("tag_name") or "")
		assets = release.get("assets") or []
		if not isinstance(assets, list):
			continue
		for asset in assets:
			if not isinstance(asset, dict):
				continue
			if str(asset.get("name") or "") != "tesseract.x86_64":
				continue
			url = str(asset.get("browser_download_url") or "")
			if not url.startswith("https://"):
				continue
			version = tag.removeprefix("tesseract-") or tag
			return ResolvedArtifact(
				name="tesseract",
				version=version,
				url=url,
				sha256="",
				kind="binary",
				notes=f"DanielMYT tesseract-static {tag} (resolved at install time).",
			)
	raise RuntimeError("no tesseract.x86_64 asset found on DanielMYT/tesseract-static")


def resolve_tesseract_windows() -> ResolvedArtifact:
	releases = _http_json(_UB_MANNHEIM_RELEASES)
	if not isinstance(releases, list):
		raise RuntimeError("unexpected GitHub releases payload for UB-Mannheim/tesseract")
	for release in releases:
		if not isinstance(release, dict):
			continue
		if release.get("draft") or release.get("prerelease"):
			continue
		tag = str(release.get("tag_name") or "")
		assets = release.get("assets") or []
		if not isinstance(assets, list):
			continue
		for asset in assets:
			if not isinstance(asset, dict):
				continue
			name = str(asset.get("name") or "")
			if not _W64_SETUP.match(name):
				continue
			url = str(asset.get("browser_download_url") or "")
			if not url.startswith("https://"):
				continue
			version = tag.lstrip("v") or tag
			return ResolvedArtifact(
				name="tesseract",
				version=version,
				url=url,
				sha256="",
				kind="nsis_installer",
				notes=f"UB-Mannheim {tag} (resolved at install time).",
			)
	raise RuntimeError("no tesseract-ocr-w64-setup asset found on UB-Mannheim/tesseract")


def _brew_bottle_tag_preference(*, machine: str) -> tuple[str, ...]:
	if machine == "arm64":
		return ("arm64_sonoma", "arm64_sequoia", "arm64_tahoe")
	if machine == "x86_64":
		return ("sonoma", "ventura", "monterey")
	raise RuntimeError(f"unsupported Darwin machine for brew bottles: {machine}")


def resolve_tesseract_brew_bottles(*, machine: str | None = None) -> tuple[BrewBottle, ...]:
	host_machine = machine or _normalize_machine(platform.machine())
	prefs = _brew_bottle_tag_preference(machine=host_machine)
	bottles: list[BrewBottle] = []
	for formula in _DARWIN_TESSERACT_FORMULAS:
		payload = _http_json(_BREW_FORMULA.format(formula=formula))
		if not isinstance(payload, dict):
			raise RuntimeError(f"unexpected brew formula payload for {formula}")
		version = str((payload.get("versions") or {}).get("stable") or payload.get("versions") or "")
		files = ((payload.get("bottle") or {}).get("stable") or {}).get("files") or {}
		if not isinstance(files, dict):
			raise RuntimeError(f"no bottle files for {formula}")
		chosen = None
		for tag in prefs:
			if tag in files:
				chosen = files[tag]
				break
		if chosen is None:
			raise RuntimeError(f"no matching bottle tag for {formula} (tried {', '.join(prefs)})")
		if not isinstance(chosen, dict):
			raise RuntimeError(f"unexpected bottle entry for {formula}")
		digest = str(chosen.get("sha256") or "")
		if len(digest) != 64:
			raise RuntimeError(f"invalid bottle digest for {formula}")
		bottles.append(_brew_bottle(formula, version or "unknown", digest))
	return tuple(bottles)


def resolve_tesseract() -> ResolvedArtifact:
	system, machine = _host()
	try:
		if system == "linux" and machine == "x86_64":
			return resolve_tesseract_linux()
		if system == "windows" and machine == "x86_64":
			return resolve_tesseract_windows()
		if system == "darwin" and machine in {"arm64", "x86_64"}:
			bottles = resolve_tesseract_brew_bottles(machine=machine)
			# Catalog-shaped artifact pointing at the primary tesseract bottle.
			primary = bottles[0]
			return ResolvedArtifact(
				name="tesseract",
				version=primary.version,
				url=primary.url,
				sha256=primary.sha256,
				kind="brew_bottles",
				notes=f"Homebrew core bottles ({machine}, resolved at install time).",
			)
		raise RuntimeError(f"tesseract resolve unsupported on {system}/{machine}")
	except RuntimeError:
		item = artifact("tesseract")
		return ResolvedArtifact(
			name=item.name,
			version=item.version,
			url=item.url,
			sha256=item.sha256,
			kind=item.kind,
			notes=item.notes or "catalog fallback",
		)


def resolved_to_download_artifact(resolved: ResolvedArtifact) -> DownloadArtifact:
	return DownloadArtifact(
		name=resolved.name,
		version=resolved.version,
		url=resolved.url,
		sha256=resolved.sha256,
		kind=resolved.kind,
		notes=resolved.notes,
	)


__all__ = [
	"ResolvedArtifact",
	"resolve_ffmpeg",
	"resolve_ffmpeg_btbn",
	"resolve_ffmpeg_martin_riedl",
	"resolve_tesseract",
	"resolve_tesseract_brew_bottles",
	"resolve_tesseract_linux",
	"resolve_tesseract_windows",
	"resolved_to_download_artifact",
]
