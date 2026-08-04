#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="${APP:-$ROOT/dist/srxy-installer-online.app}"

if [[ "$(uname -s)" != "Darwin" ]]; then
	echo "error: smoke script must run on Darwin" >&2
	exit 1
fi
if [[ ! -d "$APP" ]]; then
	echo "error: app bundle not found: $APP" >&2
	exit 1
fi

BIN="$APP/Contents/MacOS/srxy-online-bootstrap"
if [[ ! -x "$BIN" ]]; then
	echo "error: executable not found: $BIN" >&2
	exit 1
fi

"$BIN" --help >/dev/null
echo "online wrapper smoke OK: $APP"
