#!/usr/bin/env bash
# Build a UDZO DMG containing a single .app with an instruction background.
# Usage: build-dmg.sh <app-bundle> <output.dmg> [volume-name]
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
	echo "usage: $0 <app-bundle> <output.dmg> [volume-name]" >&2
	exit 2
fi

APP_BUNDLE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT_DMG="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
VOL_NAME="${3:-srxy Installer}"

if [[ ! -d "$APP_BUNDLE" ]]; then
	echo "error: app bundle not found: $APP_BUNDLE" >&2
	exit 1
fi
if [[ "$(uname -s)" != "Darwin" ]]; then
	echo "error: DMG packaging requires Darwin" >&2
	exit 1
fi

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/srxy-dmg-stage.XXXXXX")"
RW_DMG="$(mktemp "${TMPDIR:-/tmp}/srxy-dmg-rw.XXXXXX.dmg")"
# Finder styling requires a real /Volumes/<name> mount (custom mountpoints break background).
MOUNT_ROOT="/Volumes/${VOL_NAME}"
cleanup() {
	hdiutil detach "$MOUNT_ROOT" -quiet -force 2>/dev/null || true
	rm -rf "$STAGE"
	rm -f "$RW_DMG"
}
trap cleanup EXIT

# Detach any leftover volume with this name from a prior failed run.
if [[ -d "$MOUNT_ROOT" ]]; then
	hdiutil detach "$MOUNT_ROOT" -quiet -force 2>/dev/null || true
fi

APP_NAME="$(basename "$APP_BUNDLE")"
cp -R "$APP_BUNDLE" "$STAGE/$APP_NAME"
mkdir -p "$STAGE/.background"

python3 - "$STAGE/.background/background.png" <<'PY'
"""Write a simple instruction PNG (no third-party deps)."""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

# 5x7 block font for A-Z, a-z, 0-9, space, hyphen, comma, period, apostrophe.
_GLYPHS: dict[str, list[str]] = {
	" ": ["00000"] * 7,
	"-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
	",": ["00000", "00000", "00000", "00000", "01100", "00100", "01000"],
	".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
	"'": ["01100", "01100", "00100", "00000", "00000", "00000", "00000"],
	"D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
	"o": ["00000", "00000", "01110", "10001", "10001", "10001", "01110"],
	"u": ["00000", "00000", "10001", "10001", "10001", "10001", "01111"],
	"b": ["10000", "10000", "10110", "11001", "10001", "10001", "11110"],
	"l": ["01100", "00100", "00100", "00100", "00100", "00100", "01110"],
	"e": ["00000", "00000", "01110", "10001", "11111", "10000", "01110"],
	"c": ["00000", "00000", "01110", "10000", "10000", "10000", "01110"],
	"i": ["00100", "00000", "01100", "00100", "00100", "00100", "01110"],
	"k": ["10000", "10000", "10010", "10100", "11000", "10100", "10010"],
	"t": ["00100", "00100", "01110", "00100", "00100", "00100", "00010"],
	"h": ["10000", "10000", "10110", "11001", "10001", "10001", "10001"],
	"n": ["00000", "00000", "10110", "11001", "10001", "10001", "10001"],
	"s": ["00000", "00000", "01111", "10000", "01110", "00001", "11110"],
	"a": ["00000", "00000", "01110", "00001", "01111", "10001", "01111"],
	"r": ["00000", "00000", "10110", "11001", "10000", "10000", "10000"],
	"f": ["00110", "01000", "01000", "11100", "01000", "01000", "01000"],
	"g": ["00000", "00000", "01111", "10001", "01111", "00001", "01110"],
	"p": ["00000", "00000", "11110", "10001", "11110", "10000", "10000"],
	"I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
	"L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
}
TEXT = "Double-click the installer"
WIDTH, HEIGHT = 640, 400
SCALE = 3
FG = (36, 36, 36)
BG = (245, 245, 242)


def encode_png(path: Path, width: int, height: int, rgb: bytes):
	def chunk(tag: bytes, data: bytes) -> bytes:
		return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

	raw = b"".join(b"\x00" + rgb[y * width * 3 : (y + 1) * width * 3] for y in range(height))
	ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
	path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


pixels = bytearray(WIDTH * HEIGHT * 3)
for i in range(0, len(pixels), 3):
	pixels[i : i + 3] = bytes(BG)

glyph_w = 5 * SCALE + SCALE  # glyph + gap
text_w = len(TEXT) * glyph_w
start_x = max(0, (WIDTH - text_w) // 2)
# Bottom-aligned instruction text (with padding), horizontally centered.
start_y = max(0, HEIGHT - 7 * SCALE - 32)

for idx, ch in enumerate(TEXT):
	rows = _GLYPHS.get(ch, _GLYPHS[" "])
	ox = start_x + idx * glyph_w
	for row_i, row in enumerate(rows):
		for col_i, bit in enumerate(row):
			if bit != "1":
				continue
			for dy in range(SCALE):
				for dx in range(SCALE):
					x = ox + col_i * SCALE + dx
					y = start_y + row_i * SCALE + dy
					if 0 <= x < WIDTH and 0 <= y < HEIGHT:
						off = (y * WIDTH + x) * 3
						pixels[off : off + 3] = bytes(FG)

encode_png(Path(sys.argv[1]), WIDTH, HEIGHT, bytes(pixels))
print(f"Wrote background {sys.argv[1]}")
PY

# Size RW image with headroom for Finder metadata.
SIZE_MB="$(du -sm "$STAGE" | awk '{print int($1) + 20}')"
hdiutil create -quiet -ov -fs HFS+ -size "${SIZE_MB}m" -volname "$VOL_NAME" "$RW_DMG"
# Mount under /Volumes so Finder "tell disk …" can style the window.
hdiutil attach "$RW_DMG" -readwrite -noverify -noautoopen >/dev/null
# Wait briefly for the volume to appear.
for _ in $(seq 1 50); do
	[[ -d "$MOUNT_ROOT" ]] && break
	sleep 0.1
done
if [[ ! -d "$MOUNT_ROOT" ]]; then
	echo "error: volume did not mount at $MOUNT_ROOT" >&2
	exit 1
fi
cp -R "$STAGE/$APP_NAME" "$MOUNT_ROOT/"
mkdir -p "$MOUNT_ROOT/.background"
cp "$STAGE/.background/background.png" "$MOUNT_ROOT/.background/background.png"

# Configure Finder window: background + icon layout.
# Wrap toolbar/statusbar in try — modern macOS often returns -10006 for those,
# and an uncaught error would skip the background picture assignment.
osascript <<EOF
tell application "Finder"
	tell disk "$VOL_NAME"
		open
		set containerWindow to container window
		set current view of containerWindow to icon view
		try
			set toolbar visible of containerWindow to false
		end try
		try
			set statusbar visible of containerWindow to false
		end try
		set the bounds of containerWindow to {100, 100, 740, 500}
		set viewOptions to the icon view options of containerWindow
		set arrangement of viewOptions to not arranged
		set icon size of viewOptions to 96
		set background picture of viewOptions to file ".background:background.png"
		try
			set position of item "$APP_NAME" to {320, 160}
		end try
		update without registering applications
		delay 2
		close
	end tell
end tell
EOF

# Ensure .DS_Store is flushed before convert.
sync
sleep 1
# Eject via Finder first so view options stick, then hdiutil as fallback.
osascript <<EOF || true
tell application "Finder"
	if exists disk "$VOL_NAME" then
		eject disk "$VOL_NAME"
	end if
end tell
EOF
for _ in $(seq 1 50); do
	[[ ! -d "$MOUNT_ROOT" ]] && break
	sleep 0.1
done
if [[ -d "$MOUNT_ROOT" ]]; then
	hdiutil detach "$MOUNT_ROOT" -quiet -force || true
fi
rm -f "$OUT_DMG"
hdiutil convert "$RW_DMG" -format UDZO -imagekey zlib-level=9 -o "$OUT_DMG" >/dev/null
echo "Built $OUT_DMG"
