#!/usr/bin/env bash
# Remove unused PySide6 / Qt payload from the macOS offline installer venv.
#
# The wizard only needs QGuiApplication + QQml + Qt Quick Controls + FolderDialog.
# Usage: prune-pyside.sh <venv-or-site-packages-path>
set -euo pipefail

if [[ $# -ne 1 ]]; then
	echo "usage: $0 <venv-root-or-site-packages>" >&2
	exit 2
fi

TARGET="$1"
if [[ ! -d "$TARGET" ]]; then
	echo "error: not a directory: $TARGET" >&2
	exit 1
fi

SITE=""
if [[ -d "$TARGET/PySide6" ]]; then
	SITE="$TARGET"
else
	shopt -s nullglob
	candidates=("$TARGET"/lib/python*/site-packages)
	shopt -u nullglob
	if [[ ${#candidates[@]} -eq 0 ]]; then
		echo "error: no site-packages under $TARGET" >&2
		exit 1
	fi
	SITE="${candidates[0]}"
fi

PSIDE="$SITE/PySide6"
if [[ ! -d "$PSIDE" ]]; then
	echo "error: PySide6 not found at $PSIDE" >&2
	exit 1
fi

BEFORE_BYTES=""
if du_out="$(du -sk "$PSIDE" 2>/dev/null)"; then
	BEFORE_BYTES="$(awk '{print $1 * 1024}' <<<"$du_out")"
fi
echo "Pruning PySide6 under $PSIDE (before: $(du -sh "$PSIDE" 2>/dev/null | cut -f1 || echo unknown))…"

rm_rf() {
	local path
	for path in "$@"; do
		if [[ -e "$path" || -L "$path" ]]; then
			rm -rf "$path"
		fi
	done
}

# Dev-time tools/docs not needed at runtime.
rm_rf \
	"$PSIDE/Assistant.app" \
	"$PSIDE/Designer.app" \
	"$PSIDE/Linguist.app" \
	"$PSIDE/lupdate" \
	"$PSIDE/lrelease" \
	"$PSIDE/qmlls" \
	"$PSIDE/qmllint" \
	"$PSIDE/qmlformat" \
	"$PSIDE/qsb" \
	"$PSIDE/doc" \
	"$PSIDE/include" \
	"$PSIDE/typesystems" \
	"$PSIDE/glue" \
	"$PSIDE/metatypes" \
	"$PSIDE/Qt/metatypes" \
	"$PSIDE/Qt/libexec" \
	"$PSIDE/scripts" \
	"$PSIDE/support" \
	"$PSIDE/QtAsyncio" \
	"$PSIDE/py.typed"

shopt -s nullglob
rm_rf "$PSIDE"/*.pyi
KEEP_BINDINGS=(
	QtCore
	QtGui
	QtQml
	QtQuick
	QtQuickControls2
	QtNetwork
	QtDBus
	QtOpenGL
)
keep_binding() {
	local name="$1"
	local keep
	for keep in "${KEEP_BINDINGS[@]}"; do
		if [[ "$name" == "$keep" ]]; then
			return 0
		fi
	done
	return 1
}
for so in "$PSIDE"/*.abi3.so; do
	base="$(basename "$so" .abi3.so)"
	if ! keep_binding "$base"; then
		rm_rf "$so"
	fi
done
shopt -u nullglob

# macOS PySide ships Qt as .framework bundles under Qt/lib.
QT_LIB="$PSIDE/Qt/lib"
if [[ -d "$QT_LIB" ]]; then
	shopt -s nullglob
	for item in "$QT_LIB"/*; do
		base="$(basename "$item")"
		case "$base" in
		QtCore.framework | QtGui.framework | QtDBus.framework | QtNetwork.framework | \
			QtOpenGL.framework | QtQml.framework | QtQmlMeta.framework | QtQmlModels.framework | \
			QtQmlWorkerScript.framework | QtQmlNetwork.framework | QtQuick.framework | \
			QtQuickControls2.framework | QtQuickControls2Impl.framework | \
			QtQuickControls2Basic.framework | QtQuickControls2BasicStyleImpl.framework | \
			QtQuickControls2Fusion.framework | QtQuickControls2FusionStyleImpl.framework | \
			QtQuickControls2Material.framework | QtQuickControls2MaterialStyleImpl.framework | \
			QtQuickControls2Imagine.framework | QtQuickControls2ImagineStyleImpl.framework | \
			QtQuickControls2Universal.framework | QtQuickControls2UniversalStyleImpl.framework | \
			QtQuickControls2FluentWinUI3StyleImpl.framework | \
			QtQuickControls2MacOSStyleImpl.framework | \
			QtQuickControls2IOSStyleImpl.framework | \
			QtQuickTemplates2.framework | QtQuickLayouts.framework | \
			QtQuickDialogs2.framework | QtQuickDialogs2Utils.framework | QtQuickDialogs2QuickImpl.framework | \
			QtQuickEffects.framework | QtQuickShapes.framework | \
			QtLabsFolderListModel.framework | QtLabsQmlModels.framework | \
			QtShaderTools.framework | QtSvg.framework | QtConcurrent.framework | \
			QtVirtualKeyboard*.framework | \
			libicudata*.dylib | libicui18n*.dylib | libicuuc*.dylib | \
			libQt6Core*.dylib | libQt6Gui*.dylib | libQt6DBus*.dylib | libQt6Network*.dylib | \
			libQt6OpenGL*.dylib | libQt6Qml*.dylib | libQt6Quick*.dylib | \
			libQt6LabsFolderListModel*.dylib | libQt6LabsQmlModels*.dylib | \
			libQt6ShaderTools*.dylib | libQt6Svg*.dylib | libQt6Concurrent*.dylib)
			;;
		*)
			rm_rf "$item"
			;;
		esac
	done
	shopt -u nullglob
fi

QML="$PSIDE/Qt/qml"
if [[ -d "$QML" ]]; then
	rm_rf \
		"$QML/Qt3D" \
		"$QML/Qt5Compat" \
		"$QML/QtCharts" \
		"$QML/QtDataVisualization" \
		"$QML/QtGraphs" \
		"$QML/QtLocation" \
		"$QML/QtMultimedia" \
		"$QML/QtPositioning" \
		"$QML/QtQuick3D" \
		"$QML/QtRemoteObjects" \
		"$QML/QtScxml" \
		"$QML/QtSensors" \
		"$QML/QtTest" \
		"$QML/QtTextToSpeech" \
		"$QML/QtWebChannel" \
		"$QML/QtWebEngine" \
		"$QML/QtWebSockets" \
		"$QML/QtWebView" \
		"$QML/QtWayland"
	if [[ -d "$QML/QtQuick" ]]; then
		rm_rf \
			"$QML/QtQuick/Particles" \
			"$QML/QtQuick/Pdf" \
			"$QML/QtQuick/Scene2D" \
			"$QML/QtQuick/Scene3D" \
			"$QML/QtQuick/LocalStorage" \
			"$QML/QtQuick/Timeline" \
			"$QML/QtQuick/VectorImage" \
			"$QML/QtQuick/VirtualKeyboard" \
			"$QML/QtQuick/tooling" \
			"$QML/QtQuick/Controls/designer"
	fi
	if [[ -d "$QML/Qt/labs" ]]; then
		shopt -s nullglob
		for lab in "$QML/Qt/labs"/*; do
			case "$(basename "$lab")" in
			folderlistmodel | qmlmodels) ;;
			*) rm_rf "$lab" ;;
			esac
		done
		shopt -u nullglob
	fi
fi

PLUGINS="$PSIDE/Qt/plugins"
if [[ -d "$PLUGINS" ]]; then
	rm_rf \
		"$PLUGINS/assetimporters" \
		"$PLUGINS/canbus" \
		"$PLUGINS/designer" \
		"$PLUGINS/gamepads" \
		"$PLUGINS/geometryloaders" \
		"$PLUGINS/geoservices" \
		"$PLUGINS/iconengines" \
		"$PLUGINS/multimedia" \
		"$PLUGINS/networkinformation" \
		"$PLUGINS/platformthemes" \
		"$PLUGINS/position" \
		"$PLUGINS/printsupport" \
		"$PLUGINS/qmltooling" \
		"$PLUGINS/renderers" \
		"$PLUGINS/renderplugins" \
		"$PLUGINS/sceneparsers" \
		"$PLUGINS/scxmldatamodel" \
		"$PLUGINS/sensors" \
		"$PLUGINS/sqldrivers" \
		"$PLUGINS/texttospeech" \
		"$PLUGINS/tls" \
		"$PLUGINS/video" \
		"$PLUGINS/wayland-decoration-client" \
		"$PLUGINS/wayland-graphics-integration-client" \
		"$PLUGINS/wayland-shell-integration" \
		"$PLUGINS/webview" \
		"$PLUGINS/xcbglintegrations"
fi

# Strip remaining Mach-O payloads (best-effort).
if command -v strip >/dev/null 2>&1; then
	shopt -s nullglob
	while IFS= read -r -d '' macho; do
		if [[ -f "$macho" && ! -L "$macho" ]]; then
			strip -x "$macho" 2>/dev/null || true
		fi
	done < <(find "$PSIDE" \( -name '*.dylib' -o -name '*.so' -o -name '*.abi3.so' -o -path '*/Versions/A/Qt*' -o -path '*/Versions/A/lib*' \) -print0 2>/dev/null)
	shopt -u nullglob
fi

AFTER_BYTES=""
if du_out="$(du -sk "$PSIDE" 2>/dev/null)"; then
	AFTER_BYTES="$(awk '{print $1 * 1024}' <<<"$du_out")"
fi
AFTER_HUMAN="$(du -sh "$PSIDE" 2>/dev/null | cut -f1 || echo unknown)"
if [[ -n "${BEFORE_BYTES:-}" && -n "${AFTER_BYTES:-}" && "$BEFORE_BYTES" =~ ^[0-9]+$ && "$AFTER_BYTES" =~ ^[0-9]+$ ]]; then
	SAVED=$((BEFORE_BYTES - AFTER_BYTES))
	echo "Pruned PySide6 to $AFTER_HUMAN (saved $((SAVED / 1024 / 1024)) MiB)."
else
	echo "Pruned PySide6 to $AFTER_HUMAN."
fi
