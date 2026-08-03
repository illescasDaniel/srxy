#!/usr/bin/env bash
# Build a slim Linux AppImage for the srxy one-click online installer.
# Go bootstrap downloads uv + managed Python on first run, then hands off to
# the Python localhost installer. Does not replace the offline PySide AppImage.
# Requires: curl, uv, go. Downloads pinned appimagetool if missing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
APPDIR="${APPDIR:-$OUT_DIR/srxy-installer-online.AppDir}"
ARCH="${ARCH:-x86_64}"
APPIMAGETOOL_VERSION="${APPIMAGETOOL_VERSION:-1.9.1}"
APPIMAGETOOL_URL="${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage}"
APPIMAGETOOL_SHA256="${APPIMAGETOOL_SHA256:-ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0}"
ICON_SRC="${ICON_SRC:-$ROOT/src/srxy/resources/icons/srxy-installer-256.png}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
BOOTSTRAP_DIR="$ROOT/packaging/online-bootstrap"

cd "$ROOT"
mkdir -p "$OUT_DIR"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
	"$APPDIR/usr/share/icons/hicolor/256x256/apps" \
	"$APPDIR/usr/share/srxy"

if ! command -v uv >/dev/null 2>&1; then
	echo "error: uv is required to build the AppImage" >&2
	exit 1
fi
if ! command -v go >/dev/null 2>&1; then
	echo "error: go is required to build the online bootstrap AppImage" >&2
	exit 1
fi
if [[ ! -f "$ICON_SRC" ]]; then
	echo "error: app icon missing at $ICON_SRC" >&2
	exit 1
fi

echo "Building srxy wheel…"
WHEEL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/srxy-online-wheel.XXXXXX")"
cleanup_wheel() {
	rm -rf "$WHEEL_DIR"
}
trap cleanup_wheel EXIT
uv build --wheel --out-dir "$WHEEL_DIR"
WHEEL_PATH="$(find "$WHEEL_DIR" -maxdepth 1 -name 'srxy-*.whl' | head -n 1)"
if [[ -z "$WHEEL_PATH" || ! -f "$WHEEL_PATH" ]]; then
	echo "error: wheel not produced" >&2
	exit 1
fi
WHEEL_NAME="$(basename "$WHEEL_PATH")"
cp "$WHEEL_PATH" "$APPDIR/usr/share/srxy/$WHEEL_NAME"

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

echo "Writing bootstrap-meta.json…"
uv run python - <<PY
import json
from pathlib import Path
from srxy.adapters.inbound.installer.catalog import LINUX_X86_64_CATALOG

uv = LINUX_X86_64_CATALOG["uv"]
meta = {
	"uv_url": uv.url,
	"uv_sha256": uv.sha256,
	"python_version": "${PYTHON_VERSION}",
	"installer_version": "${INSTALLER_VERSION}",
	"srxy_version": "${VERSION}",
	"wheel_name": "${WHEEL_NAME}",
}
path = Path("${APPDIR}/usr/share/srxy/bootstrap-meta.json")
path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(path)
PY

cp "$ROOT/packaging/installer_meta.toml" "$APPDIR/usr/share/srxy/installer_meta.toml"

echo "Building Go online bootstrap…"
(
	cd "$BOOTSTRAP_DIR"
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath \
		-ldflags "-s -w -X main.version=${VERSION}" \
		-o "$APPDIR/usr/bin/srxy-online-bootstrap" .
)
chmod +x "$APPDIR/usr/bin/srxy-online-bootstrap"

echo "Smoke-testing bootstrap binary…"
"$APPDIR/usr/bin/srxy-online-bootstrap" --help >/dev/null
"$APPDIR/usr/bin/srxy-online-bootstrap" --version

cat >"$APPDIR/AppRun" <<'EOF'
#!/bin/sh
set -eu
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="$HERE"
exec "$HERE/usr/bin/srxy-online-bootstrap" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat >"$APPDIR/srxy-installer-online.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=srxy Online Installer
Comment=Install srxy from PyPI
Exec=AppRun
Icon=srxy-installer-online
Categories=Utility;
Terminal=false
EOF
cp "$APPDIR/srxy-installer-online.desktop" "$APPDIR/usr/share/applications/"

cp "$ICON_SRC" "$APPDIR/srxy-installer-online.png"
cp "$ICON_SRC" "$APPDIR/.DirIcon"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/srxy-installer-online.png"
for size in 16 32 48 64 128 512; do
	src="$ROOT/src/srxy/resources/icons/srxy-installer-${size}.png"
	if [[ -f "$src" ]]; then
		mkdir -p "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps"
		cp "$src" "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/srxy-installer-online.png"
	fi
done

TOOL="$OUT_DIR/appimagetool-${ARCH}.AppImage"
NEED_FETCH=0
if [[ ! -x "$TOOL" ]]; then
	NEED_FETCH=1
elif [[ -n "$APPIMAGETOOL_SHA256" ]]; then
	ACTUAL="$(sha256sum "$TOOL" | awk '{print $1}')"
	if [[ "$ACTUAL" != "$APPIMAGETOOL_SHA256" ]]; then
		echo "appimagetool digest mismatch; re-fetching…"
		NEED_FETCH=1
	fi
fi
if [[ "$NEED_FETCH" -eq 1 ]]; then
	echo "Fetching appimagetool ${APPIMAGETOOL_VERSION}…"
	curl -fsSL -o "$TOOL" "$APPIMAGETOOL_URL"
	chmod +x "$TOOL"
fi
if [[ -n "$APPIMAGETOOL_SHA256" ]]; then
	echo "$APPIMAGETOOL_SHA256  $TOOL" | sha256sum -c -
fi

OUTPUT="$OUT_DIR/srxy-${VERSION}-installer-online-${INSTALLER_VERSION}-${ARCH}.AppImage"
echo "AppDir size before pack: $(du -sh "$APPDIR" | cut -f1)"
echo "Packing $OUTPUT (squashfs zstd compression-level 19)…"
ARCH="$ARCH" VERSION="$VERSION" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" \
	--mksquashfs-opt -Xcompression-level \
	--mksquashfs-opt 19 \
	"$APPDIR" "$OUTPUT"
chmod +x "$OUTPUT"
echo "Built $OUTPUT ($(du -sh "$OUTPUT" | cut -f1))"

(
	cd "$OUT_DIR"
	sha256sum "$(basename "$OUTPUT")" >"$(basename "$OUTPUT").sha256"
	sha256sum "$(basename "$OUTPUT")" >SHA256SUMS-online
)
echo "Wrote $OUT_DIR/SHA256SUMS-online"
