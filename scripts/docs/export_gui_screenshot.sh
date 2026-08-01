#!/usr/bin/env bash
# Regenerate docs/images/gui.png for README and docs/gui.md.
# Mirrors the TUI docs screenshot: multi-term OR query, rich options, fixture results.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/quality/internal/lib.sh
source "$ROOT/scripts/quality/internal/lib.sh"

lib_require_venv
lib_activate_venv
cd "$ROOT"

mkdir -p docs/images

python <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Prefer a real display so grabWindow isn't blank; fall back to offscreen.
os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", ""))
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
	os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QMetaObject, Qt, QTimer, QUrl, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.app import qml_dir
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.application.search_session import SearchFinishedEvent
from srxy.domain.models import FileSearchResult, LineMatch

OUT = Path("docs/images/gui.png")


def fixture_path(relative: str) -> Path:
	return (Path("tests/fixtures/file_search") / relative).resolve()


results = [
	FileSearchResult(
		path=fixture_path("ocr/ocr_sample.png"),
		score=0.93,
		breakdown={"ocr": 0.93},
		lines=[
			LineMatch(
				line_number=1,
				text="quarterly revenue scan",
				score=0.93,
				location_kind="ocr",
				matched_term="revenue",
			)
		],
	),
	FileSearchResult(
		path=fixture_path("notes.txt"),
		score=0.91,
		breakdown={"content": 0.91},
		lines=[
			LineMatch(
				line_number=5,
				text="Unlike most amphibians, it reaches adulthood without",
				score=0.91,
				location_kind="line",
				matched_term="amphibian",
			)
		],
	),
	FileSearchResult(
		path=fixture_path("portrait.jpg"),
		score=0.82,
		breakdown={"semantic_image": 0.82},
		lines=[
			LineMatch(
				line_number=1,
				text="person",
				score=0.82,
				location_kind="semantic_image",
				matched_term="person",
			)
		],
	),
	FileSearchResult(
		path=fixture_path("samples/audio/speech_sample.mp3"),
		score=0.78,
		breakdown={"transcript": 0.78},
		lines=[
			LineMatch(
				line_number=1,
				text="thank you very much",
				score=0.78,
				location_kind="transcript",
				matched_term="thank you",
			)
		],
	),
]

app = QGuiApplication(sys.argv)
app.setApplicationName("srxy")

args = build_parser().parse_args(
	[
		'revenue | amphibian | person | "thank you"',
		"tests/fixtures/file_search",
		"--semantic-all",
		"--content-only",
		"--cli",
	]
)
controller = SearchController(args)
controller.path = "tests/fixtures/file_search"
controller.queryMode = "multi"
controller.applyOptionsJson(
	json.dumps(
		{
			"search_names": False,
			"search_contents": True,
			"semantic": True,
			"ocr": True,
			"transcribe": True,
			"semantic_image": True,
			"include_hidden": False,
			"include_noise": False,
			"include_archives": False,
			"include_subdirectories": True,
		}
	)
)
controller.termRowsJson = json.dumps(
	[
		{"term": "revenue", "join": ""},
		{"term": "amphibian", "join": "or"},
		{"term": "person", "join": "or"},
		{"term": "thank you", "join": "or"},
	]
)

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("controller", controller)
engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
roots = engine.rootObjects()
if not roots:
	raise SystemExit("failed to load Main.qml")
window = roots[0]
if not isinstance(window, QQuickWindow):
	raise SystemExit(f"unexpected root type: {type(window)}")
window.setWidth(1200)
window.setHeight(800)
window.show()
app.processEvents()

ok = QMetaObject.invokeMethod(
	window,
	"applyDemoMultiTerms",
	Qt.ConnectionType.DirectConnection,
	Q_ARG("QVariant", json.dumps(["revenue", "amphibian", "person", "thank you"])),
)
if not ok:
	raise SystemExit("applyDemoMultiTerms failed")
app.processEvents()

# Seed completed search UI (same demo results as the TUI screenshot).
if not controller.hasSearched:
	controller._has_searched = True  # noqa: SLF001
	controller.hasSearchedChanged.emit()
controller.handle_search_event_for_tests(SearchFinishedEvent(results=results, skipped_files=[]))
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
