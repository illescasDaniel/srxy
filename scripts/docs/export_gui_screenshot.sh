#!/usr/bin/env bash
# Regenerate docs/images/gui-<os>.png for README and docs/gui.md.
# Writes gui-macos.png / gui-linux.png / gui-windows.png for the host OS.
# Mirrors the TUI docs screenshot: multi-term OR query, rich options, fixture results.
#
# Prefers a real display so Material/Fluent button chrome paints into the grab.
# Falls back to offscreen + software RHI when DISPLAY/Wayland are absent/unreachable.
# If Material rounded-rect fills are still missing from grabWindow (common headless),
# composites button faces from QML background.color/radius so README stays accurate.
#
# Usage:
#   ./scripts/docs/export_gui_screenshot.sh
#   SRXY_GUI_SCREENSHOT_OS=macos ./scripts/docs/export_gui_screenshot.sh  # force slug (rare)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/quality/internal/lib.sh
source "$ROOT/scripts/quality/internal/lib.sh"

lib_require_venv
cd "$ROOT"

mkdir -p docs/images

lib_uv_run python <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def _display_env_present() -> bool:
	return bool(
		(os.environ.get("DISPLAY") or "").strip()
		or (os.environ.get("WAYLAND_DISPLAY") or "").strip()
	)


def _display_reachable() -> bool:
	"""True when DISPLAY/Wayland exist and look usable (socket + X auth).

	Agents and CI often inherit DISPLAY=:0 without XAUTHORITY / wayland access;
	prefer offscreen+software RHI over aborting on a dead compositor.
	"""
	if sys.platform in {"darwin", "win32"}:
		return True
	wayland = (os.environ.get("WAYLAND_DISPLAY") or "").strip()
	if wayland:
		runtime = (os.environ.get("XDG_RUNTIME_DIR") or "").strip()
		if runtime and Path(runtime, wayland).exists():
			return True
	display = (os.environ.get("DISPLAY") or "").strip()
	if not display:
		return False
	# X11 abstract/unix socket: :0 -> /tmp/.X11-unix/X0
	num = display.rsplit(":", 1)[-1].split(".", 1)[0]
	if num.isdigit() and Path(f"/tmp/.X11-unix/X{num}").exists():
		xauth = (os.environ.get("XAUTHORITY") or "").strip()
		if xauth and Path(xauth).is_file():
			return True
		home_auth = Path.home() / ".Xauthority"
		if home_auth.is_file():
			return True
	return False


# Prefer a real compositor. Only force offscreen when there is no usable
# display (do not setdefault QT_QPA_PLATFORM to "" — that can leave Qt with a
# blank platform string). User-set QT_QPA_PLATFORM is preserved.
_platform = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
_using_offscreen = _platform == "offscreen"
if not _platform and sys.platform not in {"darwin", "win32"}:
	if not _display_reachable():
		os.environ["QT_QPA_PLATFORM"] = "offscreen"
		_platform = "offscreen"
		_using_offscreen = True
		if _display_env_present():
			print(
				"warning: DISPLAY/Wayland set but unreachable; "
				"using QT_QPA_PLATFORM=offscreen + software RHI",
				file=sys.stderr,
			)

# Docs screenshots stay English + light regardless of host locale / dark mode.
os.environ.setdefault("SRXY_LANGUAGE", "en")
os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_THEME", "Light")
os.environ.setdefault("QT_QUICK_CONTROLS_UNIVERSAL_THEME", "Light")

# Material / Fluent button faces need a working RHI for grabToImage. Offscreen
# without an explicit backend often captures labels but not fills (Search
# vanishes as white-on-white; Options/Filters look like plain text).
if sys.platform == "win32":
	os.environ.setdefault("QSG_RHI_BACKEND", "opengl")
	os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
elif _using_offscreen:
	# Prefer software RHI so Material chrome paints without a GPU context.
	if not (os.environ.get("QSG_RHI_BACKEND") or "").strip():
		os.environ["QSG_RHI_BACKEND"] = "software"
	os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

from PySide6.QtCore import QEventLoop, QMetaObject, QRectF, QSize, Qt, QTimer, QUrl, Q_ARG
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtQml import QQmlApplicationEngine, QQmlProperty
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtSvg import QSvgRenderer

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.app import qml_dir
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.inbound.gui.qt_theme import apply_qt_quick_theme, shared_qml_import_path
from srxy.application.search_session import SearchFinishedEvent
from srxy.domain.models import FileSearchResult, LineMatch
from srxy.i18n import set_language
from srxy.i18n.qt import install_qt_translator

set_language("en")


def _os_slug() -> str:
	override = (os.environ.get("SRXY_GUI_SCREENSHOT_OS") or "").strip().lower()
	if override in {"macos", "linux", "windows"}:
		return override
	if sys.platform == "darwin":
		return "macos"
	if sys.platform == "win32":
		return "windows"
	return "linux"


OS_SLUG = _os_slug()
OUT = Path(f"docs/images/gui-{OS_SLUG}.png")


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
app.setOrganizationName("srxy")
# Segoe UI Variable often tofu's in grabs; prefer classic Segoe UI.
if sys.platform == "win32":
	families = set(QFontDatabase.families())
	app.setFont(QFont("Segoe UI" if "Segoe UI" in families else "Arial", 10))
srxy_theme = apply_qt_quick_theme(app)
install_qt_translator(app, "en")
# Pin light scheme after theme apply (host may be dark).
hints = app.styleHints()
set_scheme = getattr(hints, "setColorScheme", None)
color_scheme = getattr(Qt, "ColorScheme", None)
if callable(set_scheme) and color_scheme is not None:
	light = getattr(color_scheme, "Light", None)
	if light is not None:
		set_scheme(light)

args = build_parser().parse_args(
	[
		'revenue | amphibian | person | "thank you"',
		"tests/fixtures/file_search",
		"--semantic-all",
		"--content-only",
		"--language",
		"en",
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
engine.addImportPath(shared_qml_import_path())
engine.rootContext().setContextProperty("controller", controller)
engine.rootContext().setContextProperty("srxyTheme", srxy_theme)
engine.rootContext().setContextProperty("srxyUseNativeAlerts", False)
engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
roots = engine.rootObjects()
if not roots:
	raise SystemExit("failed to load Main.qml")
window = roots[0]
if not isinstance(window, QQuickWindow):
	raise SystemExit(f"unexpected root type: {type(window)}")
window.setWidth(1200)
# Windows Quick chrome (Fluent/Universal) is taller than Material/macOS; give results room.
window.setHeight(1000 if OS_SLUG == "windows" else 800)
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


def _find_item(name: str) -> QQuickItem:
	item = window.findChild(QQuickItem, name)
	if item is None:
		raise SystemExit(f"missing QML item {name!r}")
	return item


def _assert_button_geometry(name: str) -> QQuickItem:
	item = _find_item(name)
	if not bool(item.property("visible")):
		raise SystemExit(f"{name} is not visible")
	w = float(item.width())
	h = float(item.height())
	if w < 8 or h < 8:
		raise SystemExit(f"{name} has empty geometry ({w:.1f}x{h:.1f})")
	return item


def _color_distance(a: QColor, b: QColor) -> float:
	return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())


def _search_chrome_ok(image: QImage, search: QQuickItem) -> bool:
	"""True when Search's accent fill is visible (not white-on-white)."""
	origin = search.mapToItem(window.contentItem(), 0, 0)
	x0 = int(origin.x())
	y0 = int(origin.y())
	w = max(1, int(search.width()))
	h = max(1, int(search.height()))
	samples = [
		(x0 + w // 5, y0 + h // 2),
		(x0 + w // 2, y0 + h // 4),
		(x0 + (4 * w) // 5, y0 + h // 2),
		(x0 + w // 2, y0 + (3 * h) // 4),
	]
	bg = image.pixelColor(2, 2)
	accent = QColor(srxy_theme.accent)
	distinct = 0
	for sx, sy in samples:
		if sx < 0 or sy < 0 or sx >= image.width() or sy >= image.height():
			continue
		pix = image.pixelColor(sx, sy)
		if _color_distance(pix, bg) >= 40 and (pix.red() + pix.green() + pix.blue()) < 720:
			distinct += 1
		elif _color_distance(pix, accent) < 90:
			distinct += 1
	return distinct >= 2


def _button_face_color(btn: QQuickItem) -> QColor | None:
	bg = btn.property("background")
	if bg is None:
		return None
	color = QQmlProperty(bg, "color").read()
	return QColor(color) if isinstance(color, QColor) else None


def _button_face_radius(btn: QQuickItem) -> float:
	bg = btn.property("background")
	if bg is None:
		return 8.0
	radius = QQmlProperty(bg, "radius").read()
	return float(radius) if radius is not None else 8.0


def _button_face_rect(btn: QQuickItem) -> QRectF:
	bg = btn.property("background")
	target = bg if isinstance(bg, QQuickItem) else btn
	origin = target.mapToItem(window.contentItem(), 0, 0)
	return QRectF(origin.x(), origin.y(), float(target.width()), float(target.height()))


def _tint_svg(path: Path, color: QColor, size: QSize) -> QImage:
	renderer = QSvgRenderer(str(path))
	img = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
	img.fill(Qt.GlobalColor.transparent)
	painter = QPainter(img)
	renderer.render(painter)
	painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
	painter.fillRect(img.rect(), color)
	painter.end()
	return img


def _composite_material_buttons(image: QImage, names: list[str]):
	"""Paint Material button faces from QML props when RHI grabs omit shader fills.

	Headless offscreen/software grabs often keep IconLabel text but drop Material's
	rounded-rect backgrounds (Search vanishes as white-on-white). The QML items still
	expose the correct ``background.color`` / ``radius`` — redraw those faces and
	re-stamp label/icon so the README shot matches a real Material window.
	"""
	painter = QPainter(image)
	painter.setRenderHint(QPainter.RenderHint.Antialiasing)
	painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
	font = QFont(app.font())
	if font.pointSizeF() <= 0:
		font.setPointSize(10)
	painter.setFont(font)
	metrics = painter.fontMetrics()

	for name in names:
		btn = window.findChild(QQuickItem, name)
		if btn is None or not bool(btn.property("visible")):
			continue
		face = _button_face_color(btn)
		if face is None or not face.isValid():
			continue
		rect = _button_face_rect(btn)
		radius = _button_face_radius(btn)
		painter.setPen(Qt.PenStyle.NoPen)
		painter.setBrush(face)
		painter.drawRoundedRect(rect, radius, radius)

		# Label colour: Material paints white on highlighted faces (ignores
		# palette.buttonText). Use white for accent CTAs so the composite matches
		# a real Material window; secondary faces keep dark body text.
		highlighted = bool(btn.property("highlighted")) or bool(btn.property("accent"))
		label_color = QColor("#ffffff") if highlighted else QColor("#222222")
		text = str(btn.property("text") or "")
		icon_w = int(btn.property("icon.width") or 0)
		icon_h = int(btn.property("icon.height") or 0)
		spacing = float(btn.property("spacing") or 0)
		left_pad = float(btn.property("leftPadding") or 12)
		# ``icon.*`` is a grouped Quick property — read via QQmlProperty.
		icon = QQmlProperty(btn, "icon.source").read()
		if icon_w <= 0:
			icon_w = int(QQmlProperty(btn, "icon.width").read() or 0)
		if icon_h <= 0:
			icon_h = int(QQmlProperty(btn, "icon.height").read() or 0)
		icon_path: Path | None = None
		if icon is not None:
			url = icon if isinstance(icon, QUrl) else QUrl(str(icon))
			local = url.toLocalFile()
			candidates: list[Path] = []
			if local:
				candidates.append(Path(local))
			if url.path():
				candidates.append(qml_dir() / url.path().lstrip("/"))
			# Resolve relative Quick urls against Main.qml's directory (not the file).
			base_dir = QUrl.fromLocalFile(str(qml_dir()) + "/")
			resolved = base_dir.resolved(url)
			resolved_local = resolved.toLocalFile()
			if resolved_local:
				candidates.append(Path(resolved_local))
			for candidate in candidates:
				if candidate.is_file() and candidate.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg"}:
					icon_path = candidate
					break

		content_w = metrics.horizontalAdvance(text)
		if icon_path is not None and icon_w > 0:
			content_w += icon_w + spacing
		x = rect.x() + max(left_pad, (rect.width() - content_w) / 2)
		y_mid = rect.center().y()

		if icon_path is not None and icon_w > 0 and icon_h > 0:
			pix = _tint_svg(icon_path, label_color, QSize(icon_w, icon_h))
			painter.drawImage(
				int(x),
				int(y_mid - icon_h / 2),
				pix,
			)
			x += icon_w + spacing

		if text:
			painter.setPen(QPen(label_color))
			baseline = y_mid - metrics.height() / 2 + metrics.ascent()
			painter.drawText(int(x), int(baseline), text)

	painter.end()


def _grab_image() -> QImage:
	"""Wait for a presented frame, then grab the window (Material fills included)."""
	frame_loop = QEventLoop()

	def _on_frame():
		frame_loop.quit()

	window.frameSwapped.connect(_on_frame)
	window.update()
	QTimer.singleShot(3000, frame_loop.quit)
	frame_loop.exec()
	try:
		window.frameSwapped.disconnect(_on_frame)
	except (TypeError, RuntimeError):
		pass
	app.processEvents()
	# Extra settle: Material Dense faces sometimes land one frame after swap.
	settle = QEventLoop()
	QTimer.singleShot(200, settle.quit)
	settle.exec()
	app.processEvents()
	image = window.grabWindow()
	if image.isNull():
		raise SystemExit("grabWindow returned null image")
	return image


def grab():
	app.processEvents()
	window.update()
	app.processEvents()
	search = _assert_button_geometry("searchButton")
	_assert_button_geometry("optionsButton")
	_assert_button_geometry("filtersButton")
	_assert_button_geometry("browseButton")
	image = _grab_image()
	button_names = ["browseButton", "searchButton", "optionsButton", "filtersButton"]
	composited = False
	if not _search_chrome_ok(image, search):
		# Headless Material rounded-rect shaders often omit fills from grabWindow.
		_composite_material_buttons(image, button_names)
		composited = True
		if not _search_chrome_ok(image, search):
			raise SystemExit(
				"Search button chrome missing after Material face composite. "
				"Prefer a real DISPLAY/Wayland session. "
				f"platform={_platform or 'default'!r} "
				f"rhi={os.environ.get('QSG_RHI_BACKEND', '')!r}"
			)
	if not image.save(str(OUT), "PNG"):
		raise SystemExit(f"failed to save {OUT}")
	print(
		f"Wrote {OUT} ({OUT.stat().st_size} bytes) {image.width()}x{image.height()} "
		f"platform={_platform or 'default'} "
		f"rhi={os.environ.get('QSG_RHI_BACKEND', '') or 'default'}"
		f"{' composited-buttons' if composited else ''}"
	)
	app.quit()


# Windows font/scene settle is slower; real displays need a short settle too.
_settle_ms = 2000 if OS_SLUG == "windows" else (1200 if not _using_offscreen else 1500)
QTimer.singleShot(_settle_ms, grab)
raise SystemExit(app.exec())
PY
