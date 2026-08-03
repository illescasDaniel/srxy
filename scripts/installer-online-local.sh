#!/usr/bin/env bash
# Build a local srxy wheel and launch the online installer against it (no PyPI package fetch).
# Vendor downloads (uv / tesseract / ffmpeg) still use the network.
# Usage: uv run task installer-online-local
#        uv run task installer-online-local -- --no-build
#        SRXY_INSTALL_WHEEL=/path/to.whl uv run task installer-online-local
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${SRXY_INSTALL_LOCAL_DIR:-$ROOT/dist/installer-local}"
NO_BUILD=0
FORWARD=()

usage() {
	cat <<'EOF'
Build a local srxy wheel and launch the online installer (localhost browser UI).

Skips the PyPI package lookup by setting SRXY_INSTALL_WHEEL to the built wheel.
Vendor tools (uv, tesseract, ffmpeg) still download normally.

Usage: scripts/installer-online-local.sh [--no-build] [--] [installer-online args...]

Options:
  --no-build   Reuse an existing wheel under dist/installer-local/ (or SRXY_INSTALL_WHEEL)
  -h, --help   Show this help

Environment:
  SRXY_INSTALL_WHEEL       Use this .whl and skip building (absolute or relative path)
  SRXY_INSTALL_LOCAL_DIR   Wheel output directory (default: <repo>/dist/installer-local)
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--no-build)
		NO_BUILD=1
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	--)
		shift
		FORWARD+=("$@")
		break
		;;
	*)
		FORWARD+=("$1")
		shift
		;;
	esac
done

cd "$ROOT"

pick_newest_wheel() {
	local dir="$1"
	# Prefer versioned wheels; fall back to any .whl.
	local newest=""
	newest="$(ls -1t "$dir"/srxy-*.whl 2>/dev/null | head -n1 || true)"
	if [[ -z "$newest" ]]; then
		newest="$(ls -1t "$dir"/*.whl 2>/dev/null | head -n1 || true)"
	fi
	printf '%s' "$newest"
}

if [[ -n "${SRXY_INSTALL_WHEEL:-}" ]]; then
	WHEEL="$(cd "$(dirname "$SRXY_INSTALL_WHEEL")" && pwd)/$(basename "$SRXY_INSTALL_WHEEL")"
	if [[ ! -f "$WHEEL" ]]; then
		echo "error: SRXY_INSTALL_WHEEL=$SRXY_INSTALL_WHEEL is not a file" >&2
		exit 1
	fi
	echo "Using existing wheel: $WHEEL"
elif [[ "$NO_BUILD" -eq 1 ]]; then
	if [[ ! -d "$OUT_DIR" ]]; then
		echo "error: --no-build requires $OUT_DIR (or set SRXY_INSTALL_WHEEL)" >&2
		exit 1
	fi
	WHEEL="$(pick_newest_wheel "$OUT_DIR")"
	if [[ -z "$WHEEL" || ! -f "$WHEEL" ]]; then
		echo "error: no .whl found in $OUT_DIR (build once without --no-build)" >&2
		exit 1
	fi
	echo "Reusing wheel: $WHEEL"
else
	mkdir -p "$OUT_DIR"
	# Drop previous local wheels so we always pick the just-built artifact.
	rm -f "$OUT_DIR"/srxy-*.whl
	echo "Building wheel into $OUT_DIR …"
	uv build --wheel --out-dir "$OUT_DIR" "$ROOT"
	WHEEL="$(pick_newest_wheel "$OUT_DIR")"
	if [[ -z "$WHEEL" || ! -f "$WHEEL" ]]; then
		echo "error: uv build produced no wheel in $OUT_DIR" >&2
		exit 1
	fi
	echo "Built wheel: $WHEEL"
fi

export SRXY_INSTALL_WHEEL="$WHEEL"
exec uv run srxy-installer-online "${FORWARD[@]}"
