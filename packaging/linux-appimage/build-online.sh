#!/usr/bin/env bash
# Build a slim Linux AppImage for the srxy one-click online installer.
# Go bootstrap downloads uv + managed Python + srxy from PyPI on first run,
# then hands off to the Python localhost installer. Does not replace the
# offline PySide AppImage.
# Requires: curl, uv, go, xz (UPX unpack + AppImage wrap). Downloads pinned
# appimagetool + UPX if missing. Preferred release artifact is .AppImage.xz.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
APPDIR="${APPDIR:-$OUT_DIR/srxy-installer-online.AppDir}"
ARCH="${ARCH:-x86_64}"
APPIMAGETOOL_VERSION="${APPIMAGETOOL_VERSION:-1.9.1}"
APPIMAGETOOL_URL="${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage}"
APPIMAGETOOL_SHA256="${APPIMAGETOOL_SHA256:-ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0}"
UPX_VERSION="${UPX_VERSION:-5.2.0}"
UPX_URL="${UPX_URL:-https://github.com/upx/upx/releases/download/v${UPX_VERSION}/upx-${UPX_VERSION}-amd64_linux.tar.xz}"
UPX_SHA256="${UPX_SHA256:-3db5d3294707439db97866feab8d75d800f028f48481a40547411824da4288a1}"
ICON_SRC="${ICON_SRC:-$ROOT/src/srxy/resources/icons/srxy-installer-256.png}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
BOOTSTRAP_DIR="$ROOT/packaging/online-bootstrap"
SKIP_UPX="${SRXY_ONLINE_SKIP_UPX:-0}"
# shellcheck disable=SC2206 # intentional word-split of xz flags
SRXY_XZ_OPTS=(${SRXY_XZ_OPTS:--9e -T0})

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
if ! command -v xz >/dev/null 2>&1; then
	echo "error: xz is required to wrap the AppImage (and unpack pinned UPX)" >&2
	exit 1
fi
if [[ ! -f "$ICON_SRC" ]]; then
	echo "error: app icon missing at $ICON_SRC" >&2
	exit 1
fi

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
}
path = Path("${APPDIR}/usr/share/srxy/bootstrap-meta.json")
path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(path)
PY

cp "$ROOT/packaging/installer_meta.toml" "$APPDIR/usr/share/srxy/installer_meta.toml"

BOOTSTRAP_BIN="$APPDIR/usr/bin/srxy-online-bootstrap"
echo "Building Go online bootstrap…"
(
	cd "$BOOTSTRAP_DIR"
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath \
		-ldflags "-s -w -buildid= -X main.version=${VERSION}" \
		-o "$BOOTSTRAP_BIN" .
)
chmod +x "$BOOTSTRAP_BIN"
echo "Go binary before UPX: $(du -h "$BOOTSTRAP_BIN" | cut -f1)"

if [[ "$SKIP_UPX" != "1" ]]; then
	if ! command -v xz >/dev/null 2>&1; then
		echo "error: xz is required to unpack pinned UPX (or set SRXY_ONLINE_SKIP_UPX=1)" >&2
		exit 1
	fi
	UPX_DIR="$OUT_DIR/upx-${UPX_VERSION}-amd64_linux"
	UPX_ARCHIVE="$OUT_DIR/upx-${UPX_VERSION}-amd64_linux.tar.xz"
	UPX_BIN="$UPX_DIR/upx"
	if [[ ! -x "$UPX_BIN" ]]; then
		if [[ ! -f "$UPX_ARCHIVE" ]] || ! echo "$UPX_SHA256  $UPX_ARCHIVE" | sha256sum -c - >/dev/null 2>&1; then
			echo "Fetching UPX ${UPX_VERSION}…"
			curl -fsSL -o "$UPX_ARCHIVE" "$UPX_URL"
		fi
		echo "$UPX_SHA256  $UPX_ARCHIVE" | sha256sum -c -
		rm -rf "$UPX_DIR"
		tar -xJf "$UPX_ARCHIVE" -C "$OUT_DIR"
		if [[ ! -x "$UPX_BIN" ]]; then
			FOUND="$(find "$OUT_DIR" -maxdepth 2 -type f -name upx | head -n 1)"
			if [[ -z "$FOUND" ]]; then
				echo "error: upx binary missing after extract" >&2
				exit 1
			fi
			UPX_BIN="$FOUND"
		fi
	fi
	echo "Compressing bootstrap with UPX (--best --lzma)…"
	"$UPX_BIN" --best --lzma -q -f "$BOOTSTRAP_BIN"
	echo "Go binary after UPX: $(du -h "$BOOTSTRAP_BIN" | cut -f1)"
else
	echo "Skipping UPX (SRXY_ONLINE_SKIP_UPX=1)"
fi

echo "Smoke-testing bootstrap binary…"
"$BOOTSTRAP_BIN" --help >/dev/null
"$BOOTSTRAP_BIN" --version

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
# Cap at 256px — skip 512 for the slim online AppImage.
for size in 16 32 48 64 128 256; do
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

OUTPUT_XZ="${OUTPUT}.xz"
echo "Wrapping $OUTPUT_XZ (xz ${SRXY_XZ_OPTS[*]})…"
xz "${SRXY_XZ_OPTS[@]}" -k -f "$OUTPUT"
echo "Wrapped $OUTPUT_XZ ($(du -sh "$OUTPUT_XZ" | cut -f1))"

(
	cd "$OUT_DIR"
	sha256sum "$(basename "$OUTPUT_XZ")" >"$(basename "$OUTPUT_XZ").sha256"
	sha256sum "$(basename "$OUTPUT_XZ")" >SHA256SUMS-online
)
echo "Wrote $OUT_DIR/SHA256SUMS-online"
