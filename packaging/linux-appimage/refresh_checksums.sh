#!/usr/bin/env bash
# Refresh the pinned SHA-256 checksums in the installer download catalog.
# Downloads every catalog artifact to a temp dir, hashes it, and rewrites the
# sha256 fields in src/srxy/adapters/inbound/installer/catalog.py in place.
#
#   ./packaging/linux-appimage/refresh_checksums.sh              # all artifacts
#   ./packaging/linux-appimage/refresh_checksums.sh uv ffmpeg    # a subset
#   ./packaging/linux-appimage/refresh_checksums.sh --check      # print only
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
	echo "error: uv is required to refresh catalog checksums" >&2
	exit 1
fi

cd "$ROOT"

uv run -- python - "$@" <<'PY'
from __future__ import annotations

import argparse
import hashlib
import re
import tempfile
import urllib.request
from pathlib import Path

from srxy.adapters.inbound.installer.catalog import LINUX_X86_64_CATALOG

CATALOG_PATH = Path("src/srxy/adapters/inbound/installer/catalog.py")
CHUNK_SIZE = 1024 * 256
TIMEOUT_SECONDS = 600


def hash_url(url: str, target: Path) -> str:
	if not url.startswith("https://"):
		raise SystemExit(f"refusing non-https catalog URL: {url}")
	request = urllib.request.Request(url, headers={"User-Agent": "srxy-refresh-checksums"})
	hasher = hashlib.sha256()
	size = 0
	with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response, target.open("wb") as handle:
		while True:
			chunk = response.read(CHUNK_SIZE)
			if not chunk:
				break
			handle.write(chunk)
			hasher.update(chunk)
			size += len(chunk)
	print(f"  {size / 1048576:.1f} MiB")
	return hasher.hexdigest()


def patch_catalog(source: str, name: str, digest: str) -> str:
	pattern = re.compile(rf'(name="{re.escape(name)}",.*?sha256=")[0-9a-fA-F]*(")', re.DOTALL)
	patched, count = pattern.subn(rf"\g<1>{digest}\g<2>", source, count=1)
	if count != 1:
		raise SystemExit(f"could not locate the sha256 field for {name!r} in {CATALOG_PATH}")
	return patched


def main() -> int:
	parser = argparse.ArgumentParser(description="Refresh installer catalog SHA-256 checksums.")
	parser.add_argument("names", nargs="*", help="artifact names to refresh (default: every artifact)")
	parser.add_argument("--check", action="store_true", help="print digests without editing the catalog")
	args = parser.parse_args()

	names: list[str] = args.names or list(LINUX_X86_64_CATALOG)
	unknown = [name for name in names if name not in LINUX_X86_64_CATALOG]
	if unknown:
		raise SystemExit(f"unknown artifact(s): {', '.join(unknown)}")
	if not CATALOG_PATH.is_file():
		raise SystemExit(f"catalog not found at {CATALOG_PATH} (run from the repository root)")

	digests: dict[str, str] = {}
	with tempfile.TemporaryDirectory(prefix="srxy-checksums-") as tmp:
		for name in names:
			item = LINUX_X86_64_CATALOG[name]
			print(f"{name} {item.version}")
			print(f"  {item.url}")
			digest = hash_url(item.url, Path(tmp) / name)
			print(f"  sha256 {digest}")
			digests[name] = digest

	if args.check:
		return 0

	source = CATALOG_PATH.read_text(encoding="utf-8")
	for name, digest in digests.items():
		source = patch_catalog(source, name, digest)
	CATALOG_PATH.write_text(source, encoding="utf-8")
	print(f"Updated {CATALOG_PATH} ({len(digests)} artifact(s)).")
	return 0


raise SystemExit(main())
PY
