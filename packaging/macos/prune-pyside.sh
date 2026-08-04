#!/usr/bin/env bash
# Remove obviously-unused PySide6/Qt payload from macOS installer venv.
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

echo "Pruning PySide6 in $PSIDE ..."

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
	"$PSIDE/Qt/libexec"

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

QT_LIB="$PSIDE/Qt/lib"
if [[ -d "$QT_LIB" ]]; then
	shopt -s nullglob
	for lib in "$QT_LIB"/libQt6*.dylib "$QT_LIB"/libQt6*.6.dylib "$QT_LIB"/libav*.dylib "$QT_LIB"/libsw*.dylib; do
		base="$(basename "$lib")"
		case "$base" in
		libQt6Core* | libQt6Gui* | libQt6DBus* | libQt6Network* | \
			libQt6OpenGL* | libQt6QmlWorkerScript* | libQt6QmlNetwork* | \
			libQt6QmlMeta* | libQt6QmlModels* | libQt6Qml* | \
			libQt6QuickDialogs2Utils* | libQt6QuickDialogs2QuickImpl* | \
			libQt6QuickDialogs2* | libQt6QuickControls2* | libQt6QuickTemplates2* | \
			libQt6QuickLayouts* | libQt6Quick* | \
			libQt6LabsFolderListModel* | libQt6LabsQmlModels* | \
			libQt6ShaderTools* | libQt6Svg* | libQt6Concurrent* | \
			libicudata* | libicui18n* | libicuuc*)
			;;
		*)
			rm_rf "$lib"
			;;
		esac
	done
	shopt -u nullglob
fi

echo "PySide6 prune complete."
