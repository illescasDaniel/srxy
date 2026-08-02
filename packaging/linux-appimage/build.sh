#!/usr/bin/env bash
# Build a thin Linux AppImage for the srxy install/uninstall wizard.
# Requires: curl, uv. Downloads appimagetool (type2 static runtime) if missing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
APPDIR="${APPDIR:-$OUT_DIR/srxy-installer.AppDir}"
ARCH="${ARCH:-x86_64}"
APPIMAGETOOL_URL="${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage}"
ICON_SRC="${ICON_SRC:-$ROOT/src/srxy/resources/icons/srxy-256.png}"

cd "$ROOT"
mkdir -p "$OUT_DIR"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

if ! command -v uv >/dev/null 2>&1; then
	echo "error: uv is required to build the AppImage" >&2
	exit 1
fi

if [[ ! -f "$ICON_SRC" ]]; then
	echo "error: app icon missing at $ICON_SRC" >&2
	exit 1
fi

echo "Creating AppDir venv…"
uv venv --python 3.12 "$APPDIR/usr/venv"
uv pip install --python "$APPDIR/usr/venv/bin/python" "$ROOT"

echo "Building wheel for prefix installs…"
WHEEL_DIR="$APPDIR/usr/share/srxy"
mkdir -p "$WHEEL_DIR"
uv build --wheel --out-dir "$OUT_DIR/installer-wheels" "$ROOT"
WHEEL="$(ls -1 "$OUT_DIR/installer-wheels"/srxy-*.whl | tail -n 1)"
cp "$WHEEL" "$WHEEL_DIR/"
cp "$WHEEL" "$WHEEL_DIR/srxy.whl"
cp "$ROOT/packaging/installer_meta.toml" "$WHEEL_DIR/installer_meta.toml"

VERSION="$(
	"$APPDIR/usr/venv/bin/python" -c 'from importlib.metadata import version; print(version("srxy"))'
)"

cat >"$APPDIR/AppRun" <<'EOF'
#!/bin/sh
set -eu
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/venv/bin:${PATH:-}"
export PYTHONNOUSERSITE=1
exec "$HERE/usr/venv/bin/python" -m srxy.adapters.inbound.installer "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat >"$APPDIR/srxy-installer.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=srxy Installer
Comment=Install or uninstall srxy
Exec=AppRun
Icon=srxy-installer
Categories=Utility;
Terminal=false
EOF
cp "$APPDIR/srxy-installer.desktop" "$APPDIR/usr/share/applications/"

cp "$ICON_SRC" "$APPDIR/srxy-installer.png"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/srxy-installer.png"
# Extra sizes when available (helps desktop environments).
for size in 16 32 48 64 128 512; do
	src="$ROOT/src/srxy/resources/icons/srxy-${size}.png"
	if [[ -f "$src" ]]; then
		mkdir -p "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps"
		cp "$src" "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/srxy-installer.png"
	fi
done

TOOL="$OUT_DIR/appimagetool-${ARCH}.AppImage"
if [[ ! -x "$TOOL" ]]; then
	echo "Fetching appimagetool…"
	curl -fsSL -o "$TOOL" "$APPIMAGETOOL_URL"
	chmod +x "$TOOL"
fi

OUTPUT="$OUT_DIR/srxy-installer-${VERSION}-${ARCH}.AppImage"
echo "Packing $OUTPUT (appimagetool continuous / type2 static runtime)…"
ARCH="$ARCH" VERSION="$VERSION" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" "$OUTPUT"
chmod +x "$OUTPUT"
echo "Built $OUTPUT"
