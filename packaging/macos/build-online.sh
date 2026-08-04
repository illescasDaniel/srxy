#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
BOOTSTRAP_DIR="$ROOT/packaging/online-bootstrap"
ICON_SRC="${ICON_SRC:-$ROOT/src/srxy/resources/icons/srxy-installer-256.png}"
ICON_ICNS_NAME="srxy-installer.icns"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

if [[ "$(uname -s)" != "Darwin" ]]; then
	echo "error: macOS build scripts must run on Darwin" >&2
	exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
	echo "error: uv is required to build macOS installer wrappers" >&2
	exit 1
fi
if ! command -v go >/dev/null 2>&1; then
	echo "error: go is required to build online wrapper" >&2
	exit 1
fi
if [[ ! -f "$ICON_SRC" ]]; then
	echo "error: missing installer icon at $ICON_SRC" >&2
	exit 1
fi

build_icns() {
	local src_png="$1"
	local out_icns="$2"
	if ! command -v sips >/dev/null 2>&1 || ! command -v iconutil >/dev/null 2>&1; then
		return 1
	fi
	local tmpdir
	tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/srxy-installer-iconset.XXXXXX")"
	local iconset="$tmpdir/srxy-installer.iconset"
	mkdir -p "$iconset"
	for size in 16 32 128 256 512; do
		sips -z "$size" "$size" "$src_png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
		if [[ "$size" -le 512 ]]; then
			local size2x=$((size * 2))
			sips -z "$size2x" "$size2x" "$src_png" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
		fi
	done
	iconutil -c icns "$iconset" -o "$out_icns"
	rm -rf "$tmpdir"
}

ARCH="$(uname -m)"
case "$ARCH" in
arm64)
	GOARCH=arm64
	FILE_ARCH=arm64
	;;
x86_64)
	GOARCH=amd64
	FILE_ARCH=x86_64
	;;
*)
	echo "error: unsupported macOS arch: $ARCH" >&2
	exit 1
	;;
esac

cd "$ROOT"
mkdir -p "$OUT_DIR"

VERSION="$(
	uv run python -c 'from importlib.metadata import version; print(version("srxy"))'
)"
INSTALLER_VERSION="$(
	uv run python -c 'import tomllib, sys; from pathlib import Path; print(tomllib.loads(Path(sys.argv[1]).read_text())["installer_version"])' \
		"$ROOT/packaging/installer_meta.toml"
)"
if [[ -z "$INSTALLER_VERSION" ]]; then
	echo "error: installer_version missing from packaging/installer_meta.toml" >&2
	exit 1
fi

APP_NAME="${APP_NAME:-Srxy ${VERSION} - Installer Online ${INSTALLER_VERSION}.app}"
APP_BUNDLE="$OUT_DIR/$APP_NAME"
CONTENTS="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RES_DIR="$CONTENTS/Resources"
APPDIR="$CONTENTS"
DISPLAY_NAME="Srxy ${VERSION} - Installer Online ${INSTALLER_VERSION}"

rm -rf "$APP_BUNDLE" "$OUT_DIR/srxy-installer-online.app"
shopt -s nullglob
for stale in "$OUT_DIR"/Srxy\ *\ -\ Installer\ Online\ *.app; do
	rm -rf "$stale"
done
shopt -u nullglob

mkdir -p "$MACOS_DIR" "$RES_DIR" "$APPDIR/usr/share/srxy"

echo "Writing bootstrap-meta.json..."
uv run python - <<PY
import json
from pathlib import Path
from srxy.adapters.inbound.installer.catalog import artifact

uv = artifact("uv")
meta = {
	"uv_url": uv.url,
	"uv_sha256": uv.sha256,
	"python_version": "${PYTHON_VERSION}",
	"installer_version": "${INSTALLER_VERSION}",
	"srxy_version": "${VERSION}",
}
path = Path("${APPDIR}/usr/share/srxy/bootstrap-meta.json")
path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(path)
PY
cp "$ROOT/packaging/installer_meta.toml" "$APPDIR/usr/share/srxy/installer_meta.toml"

echo "Building Go bootstrap..."
(
	cd "$BOOTSTRAP_DIR"
	CGO_ENABLED=0 GOOS=darwin GOARCH="$GOARCH" go build -trimpath \
		-ldflags "-s -w -buildid= -X main.version=${VERSION}" \
		-o "$MACOS_DIR/srxy-online-bootstrap" .
)
chmod +x "$MACOS_DIR/srxy-online-bootstrap"

cat >"$CONTENTS/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>${DISPLAY_NAME}</string>
	<key>CFBundleDisplayName</key><string>${DISPLAY_NAME}</string>
	<key>CFBundleIdentifier</key><string>com.srxy.installer.online</string>
	<key>CFBundleVersion</key><string>${INSTALLER_VERSION}</string>
	<key>CFBundleShortVersionString</key><string>${VERSION}</string>
	<key>CFBundleExecutable</key><string>srxy-online-bootstrap</string>
	<key>CFBundleIconFile</key><string>srxy-installer.icns</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>LSMinimumSystemVersion</key><string>12.0</string>
</dict>
</plist>
EOF
cp "$ICON_SRC" "$RES_DIR/srxy-installer.png"
if ! build_icns "$ICON_SRC" "$RES_DIR/$ICON_ICNS_NAME"; then
	echo "warning: could not generate $ICON_ICNS_NAME (sips/iconutil unavailable); Finder may show generic app icon" >&2
fi

DMG="$OUT_DIR/srxy-${VERSION}-installer-online-${INSTALLER_VERSION}-${FILE_ARCH}.dmg"
"$ROOT/packaging/macos/build-dmg.sh" "$APP_BUNDLE" "$DMG" "srxy Installer Online"
(
	cd "$OUT_DIR"
	shasum -a 256 "$(basename "$DMG")" >"$(basename "$DMG").sha256"
	shasum -a 256 "$(basename "$DMG")" >SHA256SUMS-macos-online
)

echo "Built $APP_BUNDLE"
echo "Built $DMG"
