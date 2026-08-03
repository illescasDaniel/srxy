#!/usr/bin/env bash
# Remove unused PySide6 / Qt payload from the installer AppDir venv.
#
# The wizard only needs QGuiApplication + QQml + Qt Quick Controls + FolderDialog.
# Usage: prune_pyside.sh <venv-or-site-packages-path>
set -euo pipefail

if [[ $# -ne 1 ]]; then
	echo "usage: $0 <venv-or-site-packages-path>" >&2
	exit 2
fi

TARGET="$1"
if [[ ! -d "$TARGET" ]]; then
	echo "error: not a directory: $TARGET" >&2
	exit 1
fi

# Resolve site-packages (accept a venv root or the site-packages dir itself).
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

BEFORE_BYTES="$(du -sb "$PSIDE" 2>/dev/null | awk '{print $1}')"
echo "Pruning PySide6 under $PSIDE (before: $(du -sh "$PSIDE" | cut -f1))…"

rm_rf() {
	local path
	for path in "$@"; do
		if [[ -e "$path" || -L "$path" ]]; then
			rm -rf "$path"
		fi
	done
}

# --- Dev tools / docs / headers (never needed at runtime) ---
rm_rf \
	"$PSIDE/assistant" \
	"$PSIDE/designer" \
	"$PSIDE/linguist" \
	"$PSIDE/lupdate" \
	"$PSIDE/lrelease" \
	"$PSIDE/qmlls" \
	"$PSIDE/qmllint" \
	"$PSIDE/qmlformat" \
	"$PSIDE/qsb" \
	"$PSIDE/balsam" \
	"$PSIDE/balsamui" \
	"$PSIDE/doc" \
	"$PSIDE/include" \
	"$PSIDE/typesystems" \
	"$PSIDE/glue" \
	"$PSIDE/metatypes" \
	"$PSIDE/Qt/metatypes" \
	"$PSIDE/Qt/libexec" \
	"$PSIDE/lib" \
	"$PSIDE/scripts" \
	"$PSIDE/support" \
	"$PSIDE/QtAsyncio" \
	"$PSIDE/py.typed" \
	"$PSIDE/__feature__.pyi" \
	"$PSIDE/_git_pyside_version.py"

# Drop stub / type files and unused Python extension modules.
shopt -s nullglob
rm_rf "$PSIDE"/*.pyi
# Keep only bindings the installer imports (or that Quick/QML loads).
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

# --- Unused Qt shared libraries ---
QT_LIB="$PSIDE/Qt/lib"
if [[ -d "$QT_LIB" ]]; then
	shopt -s nullglob
	for lib in "$QT_LIB"/libQt6*.so* "$QT_LIB"/libav*.so* "$QT_LIB"/libQt6FFmpegStub*; do
		base="$(basename "$lib")"
		case "$base" in
		# Keep essentials for QGui + Quick + Dialogs + FolderDialog + platforms.
		libQt6Core.so* | libQt6Gui.so* | libQt6DBus.so* | libQt6Network.so* | \
			libQt6OpenGL.so* | libQt6Qml.so* | libQt6QmlMeta.so* | libQt6QmlModels.so* | \
			libQt6QmlWorkerScript.so* | libQt6QmlNetwork.so* | libQt6Quick.so* | \
			libQt6QuickControls2.so* | libQt6QuickControls2Impl.so* | \
			libQt6QuickControls2Basic.so* | libQt6QuickControls2BasicStyleImpl.so* | \
			libQt6QuickControls2Fusion.so* | libQt6QuickControls2FusionStyleImpl.so* | \
			libQt6QuickControls2Material.so* | libQt6QuickControls2MaterialStyleImpl.so* | \
			libQt6QuickControls2Imagine.so* | libQt6QuickControls2ImagineStyleImpl.so* | \
			libQt6QuickControls2Universal.so* | libQt6QuickControls2UniversalStyleImpl.so* | \
			libQt6QuickControls2FluentWinUI3StyleImpl.so* | \
			libQt6QuickTemplates2.so* | libQt6QuickLayouts.so* | \
			libQt6QuickDialogs2.so* | libQt6QuickDialogs2Utils.so* | libQt6QuickDialogs2QuickImpl.so* | \
			libQt6QuickEffects.so* | libQt6QuickShapes.so* | \
			libQt6LabsFolderListModel.so* | libQt6LabsQmlModels.so* | \
			libQt6ShaderTools.so* | libQt6Svg.so* | libQt6Concurrent.so* | \
			libQt6XcbQpa.so* | libQt6EglFSDeviceIntegration.so* | libQt6EglFsKmsSupport.so* | \
			libQt6WaylandClient.so* | libQt6WlShellIntegration.so* | \
			libQt6WaylandEglClientHwIntegration.so* | \
			libicudata.so* | libicui18n.so* | libicuuc.so*)
			;;
		*)
			rm_rf "$lib"
			;;
		esac
	done
	shopt -u nullglob
fi

# --- Unused QML modules ---
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
	# Trim heavy / unused QtQuick submodules; keep Controls, Dialogs, Layouts, Window, Templates.
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
	# Labs: FolderDialog needs folderlistmodel; drop the rest.
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

# --- Unused plugins ---
PLUGINS="$PSIDE/Qt/plugins"
if [[ -d "$PLUGINS" ]]; then
	rm_rf \
		"$PLUGINS/assetimporters" \
		"$PLUGINS/canbus" \
		"$PLUGINS/designer" \
		"$PLUGINS/geometryloaders" \
		"$PLUGINS/geoservices" \
		"$PLUGINS/multimedia" \
		"$PLUGINS/position" \
		"$PLUGINS/printsupport" \
		"$PLUGINS/qmllint" \
		"$PLUGINS/qmltooling" \
		"$PLUGINS/renderers" \
		"$PLUGINS/renderplugins" \
		"$PLUGINS/sceneparsers" \
		"$PLUGINS/scxmldatamodel" \
		"$PLUGINS/sensors" \
		"$PLUGINS/sqldrivers" \
		"$PLUGINS/texttospeech" \
		"$PLUGINS/vectorimageformats" \
		"$PLUGINS/webview"
fi

# Optional strip of remaining native libs (ignore failures on exotic ELFs).
if command -v strip >/dev/null 2>&1; then
	shopt -s nullglob
	for so in "$PSIDE"/*.abi3.so "$PSIDE"/Qt/lib/*.so* "$PSIDE"/Qt/plugins/*/*.so "$PSIDE"/Qt/qml/*/*.so "$PSIDE"/Qt/qml/*/*/*.so; do
		if [[ -f "$so" && ! -L "$so" ]]; then
			strip --strip-unneeded "$so" 2>/dev/null || true
		fi
	done
	shopt -u nullglob
fi

AFTER_BYTES="$(du -sb "$PSIDE" 2>/dev/null | awk '{print $1}')"
AFTER_HUMAN="$(du -sh "$PSIDE" | cut -f1)"
if [[ -n "${BEFORE_BYTES:-}" && -n "${AFTER_BYTES:-}" && "$BEFORE_BYTES" =~ ^[0-9]+$ && "$AFTER_BYTES" =~ ^[0-9]+$ ]]; then
	SAVED=$((BEFORE_BYTES - AFTER_BYTES))
	echo "Pruned PySide6 to $AFTER_HUMAN (saved $((SAVED / 1024 / 1024)) MiB)."
else
	echo "Pruned PySide6 to $AFTER_HUMAN."
fi
