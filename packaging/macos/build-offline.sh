#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
APP_NAME="${APP_NAME:-srxy-installer-offline.app}"
APP_BUNDLE="$OUT_DIR/$APP_NAME"
CONTENTS="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RES_DIR="$CONTENTS/Resources"
APPDIR="$CONTENTS"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
ICON_SRC="${ICON_SRC:-$ROOT/src/srxy/resources/icons/srxy-installer-256.png}"
ICON_ICNS_NAME="srxy-installer.icns"

if [[ "$(uname -s)" != "Darwin" ]]; then
	echo "error: macOS build scripts must run on Darwin" >&2
	exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
	echo "error: uv is required to build macOS installer wrappers" >&2
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

cd "$ROOT"
mkdir -p "$OUT_DIR"
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR" "$RES_DIR" "$APPDIR/usr/share/srxy"

echo "Installing managed Python ${PYTHON_VERSION}..."
export UV_PYTHON_PREFERENCE=only-managed
export UV_LINK_MODE=copy
uv python install "$PYTHON_VERSION" --install-dir "$RES_DIR/python" --no-bin
APP_PYTHON="$(
	python3 - "$RES_DIR/python" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
candidates = sorted(root.rglob("python3")) + sorted(root.rglob("python"))
for candidate in candidates:
	if candidate.is_file():
		print(candidate)
		break
PY
)"
if [[ -z "$APP_PYTHON" || ! -x "$APP_PYTHON" ]]; then
	echo "error: managed python not found under $RES_DIR/python" >&2
	exit 1
fi

echo "Creating bundled venv..."
uv venv --python "$APP_PYTHON" --link-mode copy "$RES_DIR/venv"
VENV_PY="$RES_DIR/venv/bin/python"
uv pip install --python "$VENV_PY" "PySide6>=6.6"
uv pip install --python "$VENV_PY" --no-deps "$ROOT"
"$ROOT/packaging/macos/prune-pyside.sh" "$RES_DIR/venv"

echo "Building wheel for offline installer payload..."
rm -rf "$OUT_DIR/macos-installer-wheels"
mkdir -p "$OUT_DIR/macos-installer-wheels"
uv build --wheel --out-dir "$OUT_DIR/macos-installer-wheels" "$ROOT"
shopt -s nullglob
BUILT_WHEELS=("$OUT_DIR/macos-installer-wheels"/srxy-*.whl)
shopt -u nullglob
if [[ ${#BUILT_WHEELS[@]} -ne 1 || ! -f "${BUILT_WHEELS[0]}" ]]; then
	echo "error: expected exactly one wheel in $OUT_DIR/macos-installer-wheels" >&2
	exit 1
fi
WHEEL="${BUILT_WHEELS[0]}"
cp "$WHEEL" "$APPDIR/usr/share/srxy/"
cp "$WHEEL" "$APPDIR/usr/share/srxy/srxy.whl"
cp "$ROOT/packaging/installer_meta.toml" "$APPDIR/usr/share/srxy/installer_meta.toml"

VERSION="$("$VENV_PY" -c 'from importlib.metadata import version; print(version("srxy"))')"
INSTALLER_VERSION="$(
	"$VENV_PY" -c 'import tomllib, sys; from pathlib import Path; print(tomllib.loads(Path(sys.argv[1]).read_text())["installer_version"])' \
		"$ROOT/packaging/installer_meta.toml"
)"

cat >"$MACOS_DIR/srxy-installer-offline" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
THIS="$0"
CONTENTS="$(cd "$(dirname "$THIS")/.." && pwd)"
export APPDIR="$CONTENTS"
export PYTHONNOUSERSITE=1
exec "$CONTENTS/Resources/venv/bin/python" -m srxy.adapters.inbound.installer "$@"
EOF
chmod +x "$MACOS_DIR/srxy-installer-offline"

cp "$ICON_SRC" "$RES_DIR/srxy-installer.png"
if ! build_icns "$ICON_SRC" "$RES_DIR/$ICON_ICNS_NAME"; then
	echo "warning: could not generate $ICON_ICNS_NAME (sips/iconutil unavailable); Finder may show generic app icon" >&2
fi
cat >"$CONTENTS/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>srxy Installer Offline</string>
	<key>CFBundleDisplayName</key><string>srxy Installer Offline</string>
	<key>CFBundleIdentifier</key><string>com.srxy.installer.offline</string>
	<key>CFBundleVersion</key><string>1</string>
	<key>CFBundleShortVersionString</key><string>1</string>
	<key>CFBundleExecutable</key><string>srxy-installer-offline</string>
	<key>CFBundleIconFile</key><string>srxy-installer.icns</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>LSMinimumSystemVersion</key><string>12.0</string>
</dict>
</plist>
EOF

ARCHIVE="$OUT_DIR/srxy-${VERSION}-installer-macos-offline-${INSTALLER_VERSION}.app.tar.gz"
python3 - "$OUT_DIR" "$APP_NAME" "$ARCHIVE" <<'PY'
import tarfile
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
app_name = sys.argv[2]
archive = Path(sys.argv[3])
with tarfile.open(archive, mode="w:gz", compresslevel=9) as tf:
	tf.add(out_dir / app_name, arcname=app_name)
PY
(
	cd "$OUT_DIR"
	shasum -a 256 "$(basename "$ARCHIVE")" >"$(basename "$ARCHIVE").sha256"
	shasum -a 256 "$(basename "$ARCHIVE")" >SHA256SUMS-macos-offline
)

echo "Built $APP_BUNDLE"
echo "Built $ARCHIVE"
