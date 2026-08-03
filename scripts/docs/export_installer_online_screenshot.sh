#!/usr/bin/env bash
# Regenerate docs/images/installer-online.png for README (localhost web installer UI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/quality/internal/lib.sh
source "$ROOT/scripts/quality/internal/lib.sh"

lib_require_venv
cd "$ROOT"

mkdir -p docs/images

# Prefer a real display; fall back to offscreen (WebEngine uses software render).
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
	export QT_QPA_PLATFORM=offscreen
fi

# Generic home so the Install-to field is not a machine-specific path.
export HOME="${SRXY_SCREENSHOT_HOME:-/home/user}"

lib_uv_run python <<'PY'
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

from srxy.adapters.inbound.installer_online.server import create_online_installer_server
from srxy.i18n import set_language

OUT = Path("docs/images/installer-online.png")

os.environ.setdefault("SRXY_SKIP_UPDATE_CHECK", "1")
os.environ.setdefault("SRXY_LANGUAGE", "en")
set_language("en")

url, _session, server = create_online_installer_server()
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

app = QApplication(sys.argv)
app.setApplicationName("srxy-installer-online-screenshot")

view = QWebEngineView()
view.resize(900, 820)


def grab_when_ready(attempt: int = 0):
	def _check(subtitle: object):
		text = str(subtitle or "").strip()
		if not text and attempt < 50:
			QTimer.singleShot(100, lambda: grab_when_ready(attempt + 1))
			return
		app.processEvents()
		pixmap = view.grab()
		if pixmap.isNull():
			raise SystemExit("view.grab() returned null image")
		if not pixmap.save(str(OUT), "PNG"):
			raise SystemExit(f"failed to save {OUT}")
		print(f"Wrote {OUT} ({OUT.stat().st_size} bytes) {pixmap.width()}x{pixmap.height()}")
		server.shutdown()
		app.quit()

	view.page().runJavaScript(
		"(document.getElementById('subtitle') || {}).textContent || ''",
		_check,
	)


def on_load(ok: bool):
	if not ok:
		server.shutdown()
		raise SystemExit(f"failed to load {url}")
	QTimer.singleShot(300, grab_when_ready)


view.loadFinished.connect(on_load)
view.load(QUrl(url))
view.show()
raise SystemExit(app.exec())
PY
