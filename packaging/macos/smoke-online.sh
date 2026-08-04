#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="${APP:-}"

if [[ "$(uname -s)" != "Darwin" ]]; then
	echo "error: smoke script must run on Darwin" >&2
	exit 1
fi

if [[ -z "$APP" ]]; then
	shopt -s nullglob
	candidates=(
		"$ROOT"/dist/Srxy\ *\ -\ Installer\ Online\ *.app
		"$ROOT/dist/srxy-installer-online.app"
	)
	shopt -u nullglob
	for cand in "${candidates[@]}"; do
		if [[ -d "$cand" ]]; then
			APP="$cand"
			break
		fi
	done
fi

if [[ -z "${APP:-}" || ! -d "$APP" ]]; then
	echo "error: app bundle not found (set APP=…)" >&2
	exit 1
fi

BIN="$APP/Contents/MacOS/srxy-online-bootstrap"
if [[ ! -x "$BIN" ]]; then
	echo "error: executable not found: $BIN" >&2
	exit 1
fi

"$BIN" --help >/dev/null
echo "online wrapper smoke OK: $APP"
