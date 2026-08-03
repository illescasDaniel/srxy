#!/usr/bin/env bash
# Smoke-test a built srxy online installer AppImage.
#
# Usage:
#   ./packaging/linux-appimage/smoke-appimage-online.sh [path-to-AppImage]
#
# When no path is given, picks the newest dist/srxy-*-installer-online-*-x86_64.AppImage.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"

if [[ $# -ge 1 ]]; then
	APPIMAGE="$1"
else
	shopt -s nullglob
	candidates=("$OUT_DIR"/srxy-*-installer-online-*-x86_64.AppImage)
	shopt -u nullglob
	if [[ ${#candidates[@]} -eq 0 ]]; then
		echo "error: no online AppImage found under $OUT_DIR; build first or pass a path" >&2
		exit 1
	fi
	APPIMAGE="$(find "$OUT_DIR" -maxdepth 1 -name 'srxy-*-installer-online-*-x86_64.AppImage' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
fi

if [[ -z "${APPIMAGE:-}" || ! -f "$APPIMAGE" ]]; then
	echo "error: AppImage not found: ${APPIMAGE:-<empty>}" >&2
	exit 1
fi
if [[ ! -x "$APPIMAGE" ]]; then
	chmod +x "$APPIMAGE"
fi

SMOKE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/srxy-appimage-online-smoke.XXXXXX")"
cleanup() {
	rm -rf "$SMOKE_HOME"
}
trap cleanup EXIT

SAFE_PATH="/usr/bin:/bin"
export HOME="$SMOKE_HOME"
export PATH="$SAFE_PATH"
unset VIRTUAL_ENV UV_PYTHON UV_PYTHON_PREFERENCE PYTHONPATH PYTHONHOME || true
mkdir -p "$HOME"

echo "Smoke testing $APPIMAGE (HOME=$HOME)…"
export APPIMAGE_EXTRACT_AND_RUN=1
"$APPIMAGE" --help >/dev/null
"$APPIMAGE" --version

echo "smoke-appimage-online: OK"
