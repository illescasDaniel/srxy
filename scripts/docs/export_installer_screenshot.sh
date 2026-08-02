#!/usr/bin/env bash
# Regenerate docs/images/installer.png for README (installer mode page).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/quality/internal/lib.sh
source "$ROOT/scripts/quality/internal/lib.sh"

lib_require_venv
cd "$ROOT"

mkdir -p docs/images

lib_uv_run python <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path

# Prefer a real display so grabWindow isn't blank; fall back to offscreen.
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
	os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from srxy.adapters.inbound.gui.app_icon import apply_app_icon
from srxy.adapters.inbound.installer.app import qml_dir
from srxy.adapters.inbound.installer.controller import InstallerController
from srxy.i18n import set_language
from srxy.i18n.qt import install_qt_translator

OUT = Path("docs/images/installer.png")

os.environ.setdefault("SRXY_SKIP_UPDATE_CHECK", "1")
os.environ.setdefault("SRXY_LANGUAGE", "en")
set_language("en")

app = QGuiApplication(sys.argv)
app.setApplicationName("srxy-installer")
apply_app_icon(app)
install_qt_translator(app, "en")

engine = QQmlApplicationEngine()
controller = InstallerController()
controller.setLanguage("en")
engine.rootContext().setContextProperty("controller", controller)
engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
roots = engine.rootObjects()
if not roots:
	raise SystemExit("failed to load installer Main.qml")
window = roots[0]
if not isinstance(window, QQuickWindow):
	raise SystemExit(f"unexpected root type: {type(window)}")

# Match the wizard's natural size a bit wider for README readability.
window.setWidth(720)
window.setHeight(520)
window.show()
app.processEvents()


def grab():
	app.processEvents()
	image = window.grabWindow()
	if image.isNull():
		raise SystemExit("grabWindow returned null image")
	if not image.save(str(OUT), "PNG"):
		raise SystemExit(f"failed to save {OUT}")
	print(f"Wrote {OUT} ({OUT.stat().st_size} bytes) {image.width()}x{image.height()}")
	app.quit()


QTimer.singleShot(900, grab)
raise SystemExit(app.exec())
PY
