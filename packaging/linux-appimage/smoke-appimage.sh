#!/usr/bin/env bash
# Smoke-test a built srxy installer AppImage without relying on host uv Python.
#
# Usage:
#   ./packaging/linux-appimage/smoke-appimage.sh [path-to-AppImage]
#
# When no path is given, picks the newest dist/srxy-installer-*-x86_64.AppImage.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"

if [[ $# -ge 1 ]]; then
	APPIMAGE="$1"
else
	shopt -s nullglob
	candidates=("$OUT_DIR"/srxy-installer-*-x86_64.AppImage)
	shopt -u nullglob
	if [[ ${#candidates[@]} -eq 0 ]]; then
		echo "error: no AppImage found under $OUT_DIR; build first or pass a path" >&2
		exit 1
	fi
	# Prefer newest mtime without relying on ls (SC2012).
	APPIMAGE="$(find "$OUT_DIR" -maxdepth 1 -name 'srxy-installer-*-x86_64.AppImage' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
fi

if [[ -z "${APPIMAGE:-}" || ! -f "$APPIMAGE" ]]; then
	echo "error: AppImage not found: ${APPIMAGE:-<empty>}" >&2
	exit 1
fi
if [[ ! -x "$APPIMAGE" ]]; then
	chmod +x "$APPIMAGE"
fi

# Isolate HOME so a broken AppDir that still symlinks into the real host
# uv Python cache cannot silently succeed via the developer's install.
SMOKE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/srxy-appimage-smoke.XXXXXX")"
cleanup() {
	rm -rf "$SMOKE_HOME"
}
trap cleanup EXIT

# Drop host uv / project venv from PATH; keep a minimal system PATH.
SAFE_PATH="/usr/bin:/bin"
export HOME="$SMOKE_HOME"
export PATH="$SAFE_PATH"
unset VIRTUAL_ENV UV_PYTHON UV_PYTHON_PREFERENCE PYTHONPATH PYTHONHOME || true
mkdir -p "$HOME"

# Headless Qt for --help/--version (no display in CI).
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

echo "Smoke testing $APPIMAGE (HOME=$HOME)…"
# Installer entry points: --help / --version should exit 0 without a display.
# APPIMAGE_EXTRACT_AND_RUN avoids fuse requirements in CI/containers.
export APPIMAGE_EXTRACT_AND_RUN=1
"$APPIMAGE" --help >/dev/null
"$APPIMAGE" --version

echo "smoke-appimage: OK"
