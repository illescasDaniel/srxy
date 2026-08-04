#!/usr/bin/env bash
# Build the online macOS installer, then locally sign, notarize, and staple it.
# Local-only — CI builds via build-online.sh directly and never signs.
# See packaging/macos/signing.env.example for one-time setup.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"

"$ROOT/packaging/macos/build-online.sh"

shopt -s nullglob
APP=""
for cand in "$OUT_DIR"/Srxy\ *\ -\ Installer\ Online\ *.app; do
	APP="$cand"
done
shopt -u nullglob
if [[ -z "$APP" ]]; then
	echo "error: could not find the just-built online .app under $OUT_DIR" >&2
	exit 1
fi

FILE_ARCH="$(uname -m)"
VERSION="$(uv run python -c 'from importlib.metadata import version; print(version("srxy"))')"
INSTALLER_VERSION="$(
	uv run python -c 'import tomllib, sys; from pathlib import Path; print(tomllib.loads(Path(sys.argv[1]).read_text())["installer_version"])' \
		"$ROOT/packaging/installer_meta.toml"
)"
DMG="$OUT_DIR/srxy-${VERSION}-installer-online-${INSTALLER_VERSION}-${FILE_ARCH}.dmg"

"$ROOT/packaging/macos/sign-release.sh" "$APP" "$DMG" "srxy Installer Online"
