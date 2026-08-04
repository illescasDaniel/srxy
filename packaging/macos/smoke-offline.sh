#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="${APP:-}"

if [[ "$(uname -s)" != "Darwin" ]]; then
	echo "error: smoke script must run on Darwin" >&2
	exit 1
fi

if [[ -z "$APP" ]]; then
	# Prefer versioned display name; fall back to legacy bundle name.
	shopt -s nullglob
	for cand in "$ROOT"/dist/Srxy\ *\ -\ Installer\ *.app; do
		case "$(basename "$cand")" in
		*"Installer Online"*) continue ;;
		esac
		if [[ -d "$cand" ]]; then
			APP="$cand"
			break
		fi
	done
	if [[ -z "${APP:-}" && -d "$ROOT/dist/srxy-installer-offline.app" ]]; then
		APP="$ROOT/dist/srxy-installer-offline.app"
	fi
	shopt -u nullglob
fi

if [[ -z "${APP:-}" || ! -d "$APP" ]]; then
	echo "error: app bundle not found (set APP=…)" >&2
	exit 1
fi

BIN="$APP/Contents/MacOS/srxy-installer-offline"
VENV_PY="$APP/Contents/Resources/venv/bin/python"
if [[ ! -x "$BIN" ]]; then
	echo "error: executable not found: $BIN" >&2
	exit 1
fi
if [[ ! -x "$VENV_PY" ]]; then
	echo "error: bundled python not found: $VENV_PY" >&2
	exit 1
fi

"$BIN" --version >/dev/null

echo "Smoke-testing pruned Qt Quick Controls (offscreen)…"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
"$VENV_PY" -c 'import srxy.adapters.inbound.installer'
"$VENV_PY" <<'PY'
from __future__ import annotations

import sys

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
qml = b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
ApplicationWindow {
	visible: false
	width: 100
	height: 100
	FolderDialog {}
}
"""
engine.loadData(QByteArray(qml), QUrl())
if not engine.rootObjects():
	raise SystemExit("offline smoke: failed to load QtQuick.Controls QML")
print("offline QML Controls smoke OK")
PY

echo "offline wrapper smoke OK: $APP"
