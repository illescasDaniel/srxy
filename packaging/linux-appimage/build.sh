#!/usr/bin/env bash
# Build a thin Linux AppImage for the srxy install/uninstall wizard.
# Requires: curl, uv. Downloads pinned appimagetool (type2 static runtime) if missing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
APPDIR="${APPDIR:-$OUT_DIR/srxy-installer.AppDir}"
ARCH="${ARCH:-x86_64}"
# Pin appimagetool to an immutable release tag (never "continuous").
APPIMAGETOOL_VERSION="${APPIMAGETOOL_VERSION:-1.9.1}"
APPIMAGETOOL_URL="${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage}"
# SHA-256 of appimagetool-x86_64.AppImage @ 1.9.1 (override when bumping the pin).
APPIMAGETOOL_SHA256="${APPIMAGETOOL_SHA256:-ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0}"
ICON_SRC="${ICON_SRC:-$ROOT/src/srxy/resources/icons/srxy-installer-256.png}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

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

echo "Installing managed CPython ${PYTHON_VERSION} into AppDir…"
# Install a full interpreter tree under the AppDir so the AppImage never
# depends on ~/.local/share/uv/python from the build host.
export UV_PYTHON_PREFERENCE=only-managed
export UV_LINK_MODE=copy
uv python install "$PYTHON_VERSION" --install-dir "$APPDIR/usr/python" --no-bin
APP_PYTHON="$(find "$APPDIR/usr/python" -type f \( -name "python${PYTHON_VERSION}" -o -name python3 -o -name python \) | head -n 1)"
if [[ -z "$APP_PYTHON" || ! -x "$APP_PYTHON" ]]; then
	echo "error: managed python not found under $APPDIR/usr/python" >&2
	find "$APPDIR/usr/python" -maxdepth 4 -type f -name 'python*' >&2 || true
	exit 1
fi
echo "Creating relocatable AppDir venv from $APP_PYTHON…"
uv venv --python "$APP_PYTHON" --relocatable --link-mode copy "$APPDIR/usr/venv"
uv pip install --python "$APPDIR/usr/venv/bin/python" "$ROOT"

# Fail closed if the venv python still points at the build host uv cache / home.
VENV_PY="$APPDIR/usr/venv/bin/python"
RESOLVED_PY="$(readlink -f "$VENV_PY" 2>/dev/null || realpath "$VENV_PY")"
case "$RESOLVED_PY" in
"$APPDIR"/*) ;;
*)
	echo "error: AppDir python is not relocatable: $VENV_PY -> $RESOLVED_PY" >&2
	echo "expected an interpreter under $APPDIR." >&2
	exit 1
	;;
esac
case "$RESOLVED_PY" in
*"/.local/share/uv/python/"*)
	echo "error: AppDir python still resolves into host uv cache: $RESOLVED_PY" >&2
	exit 1
	;;
esac
echo "AppDir python OK: $RESOLVED_PY"

echo "Building wheel for prefix installs…"
WHEEL_DIR="$APPDIR/usr/share/srxy"
mkdir -p "$WHEEL_DIR"
rm -rf "$OUT_DIR/installer-wheels"
mkdir -p "$OUT_DIR/installer-wheels"
# Fresh out-dir: pick the single wheel by glob (uv prints a relative path).
uv build --wheel --out-dir "$OUT_DIR/installer-wheels" "$ROOT"
shopt -s nullglob
BUILT_WHEELS=("$OUT_DIR/installer-wheels"/srxy-*.whl)
shopt -u nullglob
if [[ ${#BUILT_WHEELS[@]} -ne 1 || ! -f "${BUILT_WHEELS[0]}" ]]; then
	echo "error: expected exactly one wheel in $OUT_DIR/installer-wheels" >&2
	ls -la "$OUT_DIR/installer-wheels" >&2 || true
	exit 1
fi
WHEEL="${BUILT_WHEELS[0]}"
cp "$WHEEL" "$WHEEL_DIR/"
cp "$WHEEL" "$WHEEL_DIR/srxy.whl"
cp "$ROOT/packaging/installer_meta.toml" "$WHEEL_DIR/installer_meta.toml"

VERSION="$(
	"$APPDIR/usr/venv/bin/python" -c 'from importlib.metadata import version; print(version("srxy"))'
)"
INSTALLER_VERSION="$(
	"$APPDIR/usr/venv/bin/python" -c 'import tomllib, sys; from pathlib import Path; print(tomllib.loads(Path(sys.argv[1]).read_text())["installer_version"])' \
		"$ROOT/packaging/installer_meta.toml"
)"
if [[ -z "$INSTALLER_VERSION" ]]; then
	echo "error: installer_version missing from packaging/installer_meta.toml" >&2
	exit 1
fi

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
# Thumbnailers read .DirIcon; ship a real file (not only the symlink appimagetool may add).
cp "$ICON_SRC" "$APPDIR/.DirIcon"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/srxy-installer.png"
for size in 16 32 48 64 128 512; do
	src="$ROOT/src/srxy/resources/icons/srxy-installer-${size}.png"
	if [[ -f "$src" ]]; then
		mkdir -p "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps"
		cp "$src" "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/srxy-installer.png"
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

OUTPUT="$OUT_DIR/srxy-installer-${VERSION}-${INSTALLER_VERSION}-${ARCH}.AppImage"
echo "Packing $OUTPUT…"
ARCH="$ARCH" VERSION="$VERSION" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" "$OUTPUT"
chmod +x "$OUTPUT"
echo "Built $OUTPUT"

# Write checksums alongside the artifact for release uploads.
(
	cd "$OUT_DIR"
	sha256sum "$(basename "$OUTPUT")" >"$(basename "$OUTPUT").sha256"
	sha256sum "$(basename "$OUTPUT")" >SHA256SUMS
)
echo "Wrote $OUT_DIR/SHA256SUMS"
