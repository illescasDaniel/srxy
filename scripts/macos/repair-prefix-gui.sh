#!/usr/bin/env bash
# Refresh an existing ~/Applications/srxy (or SRXY_HOME) install to match this
# worktree: reinstall package, pin PySide6==6.11.1, rewrite launcher with
# in-bundle Python (AppKit mainBundle + PYTHONHOME + SDK 26 restamp for Liquid
# Glass), clear QML disk caches.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="${SRXY_HOME:-$HOME/Applications/srxy}"
UV="${PREFIX}/vendor/uv/uv"
PY="${PREFIX}/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
	echo "error: no prefix venv at $PREFIX/.venv" >&2
	exit 1
fi
if [[ ! -x "$UV" ]]; then
	UV="$(command -v uv)"
fi

echo "Repairing GUI install at $PREFIX"
"$UV" pip install --python "$PY" --reinstall-package srxy "srxy[semantic] @ file://${ROOT}"
"$UV" pip install --python "$PY" "PySide6==6.11.1"

export SRXY_HOME="$PREFIX"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" <<'PY'
from pathlib import Path
import os

from srxy.adapters.inbound.installer.install import write_launcher, _clear_macos_qml_caches

prefix = Path(os.environ["SRXY_HOME"])
write_launcher(prefix)
_clear_macos_qml_caches()
exe = prefix / "Srxy.app/Contents/MacOS/srxy"
embedded = prefix / "Srxy.app/Contents/MacOS/SrxyPython"
raw = exe.read_bytes()
print("launcher rewritten; qml caches cleared")
print("embedded", embedded.exists())
print("bundle_exe", exe, "shebang" if raw.startswith(b"#!") else "mach-o-or-binary")
if raw.startswith(b"#!"):
	raise SystemExit("Srxy.app CFBundleExecutable must be Mach-O, not a shell script")
# Must be a distinct copy (never hardlink to uv CPython) so vtool is safe.
real_uv = (prefix / ".venv" / "bin" / "python").resolve()
if embedded.exists() and embedded.stat().st_ino == real_uv.stat().st_ino and embedded.stat().st_nlink > 1:
	raise SystemExit(
		"SrxyPython must be a copy, not a hardlink to uv CPython (vtool would mutate shared install)"
	)
PY

"$PY" -c "
import os
import PySide6
from PySide6.QtQuickControls2 import QQuickStyle
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'macOS')
QQuickStyle.setStyle('macOS')
print('PySide', PySide6.__version__, 'style', QQuickStyle.name())
"

BASE="$("$PY" -c 'import sys; print(sys.base_prefix)')"
SITE="$(ls -d "$PREFIX"/.venv/lib/python*/site-packages | head -n1)"
if [[ -z "$SITE" ]]; then
	echo "error: no site-packages under $PREFIX/.venv" >&2
	exit 1
fi
# Embedded interpreter only works with PYTHONHOME (argv[0] is inside the .app).
if ! PYTHONHOME="$BASE" PYTHONPATH="$SITE" "$PREFIX/Srxy.app/Contents/MacOS/SrxyPython" -c 'import srxy; print("srxy_ok")'; then
	echo "error: embedded SrxyPython cannot import srxy (PYTHONHOME=$BASE)" >&2
	exit 1
fi
EXE="$PREFIX/Srxy.app/Contents/MacOS/srxy"
EMBED="$PREFIX/Srxy.app/Contents/MacOS/SrxyPython"
if ! /usr/bin/strings "$EXE" | grep -q 'PYTHONHOME'; then
	echo "error: Srxy.app launcher is missing baked PYTHONHOME" >&2
	exit 1
fi
# Tahoe Liquid Glass: process image after execv must advertise sdk >= 26.
VTOOL="$(command -v vtool || true)"
if [[ -z "$VTOOL" && -x /usr/bin/vtool ]]; then
	VTOOL=/usr/bin/vtool
fi
if [[ -z "$VTOOL" ]]; then
	echo "error: vtool not found; cannot verify embedded Python SDK stamp" >&2
	exit 1
fi
BUILD_SHOW="$("$VTOOL" -show-build "$EMBED" 2>&1 || true)"
echo "$BUILD_SHOW"
if ! echo "$BUILD_SHOW" | grep -E 'sdk[[:space:]]+26(\.|$)' >/dev/null; then
	echo "error: SrxyPython must be restamped to sdk 26.x for Liquid Glass (got above)" >&2
	exit 1
fi
# Clean-env smoke: Finder-like launch must not die on missing stdlib prefix.
if ! env -i HOME="$HOME" USER="${USER:-}" PATH="/usr/bin:/bin:/usr/sbin:/sbin" "$EXE" --help >/tmp/srxy-repair-help.out 2>/tmp/srxy-repair-help.err; then
	echo "error: Srxy.app launcher failed clean-env --help" >&2
	cat /tmp/srxy-repair-help.err >&2 || true
	exit 1
fi
if grep -q "Could not find platform independent libraries" /tmp/srxy-repair-help.err /tmp/srxy-repair-help.out 2>/dev/null; then
	echo "error: Srxy.app launcher missing working PYTHONHOME (stdlib not found)" >&2
	cat /tmp/srxy-repair-help.err >&2 || true
	exit 1
fi

echo "Done. Quit Srxy fully (Cmd+Q) and relaunch from Srxy.app (not PATH/bin/srxy)."
echo "Verify: file \"$PREFIX/Srxy.app/Contents/MacOS/srxy\" should say Mach-O (not a shell script)."
echo "Verify: vtool -show-build …/SrxyPython should show sdk 26.x."
