#!/usr/bin/env python3
"""Generate macOS Srxy.app icons on Apple's app-icon grid.

Source of truth (uncompressed original):

	assets/icons/srxy.png

Apple's macOS template (Big Sur+): 1024×1024 canvas with an 824×824 art
box centered (~100 px transparent gutter on every side). Pre-mask the art
box to a continuous rounded square so Dock/Launchpad size matches system
icons. Full-bleed masked icons look ~24% oversized next to neighbors.

Linux/hicolor icons stay square under ``src/srxy/resources/icons/``.

Run from the repo root:

	task generate-macos-icons
	# or: uv run python scripts/generate_macos_icons.py

Master output (compress this if desired):

	src/srxy/resources/icons/macos/srxy.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "assets" / "icons" / "srxy.png"
ICON_DIR = ROOT / "src" / "srxy" / "resources" / "icons"
MACOS_DIR = ICON_DIR / "macos"
SIZES = [16, 32, 48, 64, 128, 256, 512]
MASTER = 1024
# Apple production template: 824 art box on 1024 canvas (100 px gutter/side).
ART_SIZE = 824
MARGIN = (MASTER - ART_SIZE) // 2
# Continuous-corner radius for the 824 art box (~185.4 px in Apple's template).
ART_CORNER_RADIUS = 185.4
# Soft plate shadow in the gutter (matches common macOS icon exports).
SHADOW_BLUR = 28
SHADOW_OFFSET_Y = 12
SHADOW_OPACITY = 90  # of 255 ≈ 35%


def squircle_mask(size: int, *, radius: float) -> Image.Image:
	"""Antialiased rounded-square alpha mask for a given art-box size."""
	scale = 4
	big = size * scale
	big_radius = radius * scale
	mask = Image.new("L", (big, big), 0)
	draw = ImageDraw.Draw(mask)
	draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big_radius, fill=255)
	return mask.resize((size, size), Image.Resampling.LANCZOS)


def render_macos_icon(src: Image.Image, *, canvas_size: int = MASTER) -> Image.Image:
	"""Place artwork on the Apple grid and mask to a squircle with gutter."""
	rgba = src.convert("RGBA")
	w, h = rgba.size
	if w != h:
		raise SystemExit(f"expected square icon, got {w}x{h}")

	scale = canvas_size / MASTER
	art_size = max(1, int(round(ART_SIZE * scale)))
	margin = max(0, (canvas_size - art_size) // 2)
	radius = ART_CORNER_RADIUS * scale
	blur = max(1, int(round(SHADOW_BLUR * scale)))
	offset_y = int(round(SHADOW_OFFSET_Y * scale))

	art = rgba.resize((art_size, art_size), Image.Resampling.LANCZOS)
	art.putalpha(squircle_mask(art_size, radius=radius))

	canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

	# Drop shadow sits in the transparent gutter so Dock sizing matches neighbors.
	shadow_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
	shadow_draw = ImageDraw.Draw(shadow_layer)
	shadow_box = (
		margin,
		margin + offset_y,
		margin + art_size - 1,
		margin + offset_y + art_size - 1,
	)
	shadow_draw.rounded_rectangle(
		shadow_box,
		radius=radius,
		fill=(0, 0, 0, SHADOW_OPACITY),
	)
	shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur))
	canvas = Image.alpha_composite(canvas, shadow_layer)
	canvas.paste(art, (margin, margin), art)
	return canvas


def main():
	if not ORIGINAL.is_file():
		raise SystemExit(f"missing original icon: {ORIGINAL}")
	base = Image.open(ORIGINAL).convert("RGBA")
	if base.size != (MASTER, MASTER):
		raise SystemExit(f"expected {MASTER}x{MASTER} master icon, got {base.size}")

	MACOS_DIR.mkdir(parents=True, exist_ok=True)
	masked_master = render_macos_icon(base)
	# Keep RGB+alpha; avoid palette quantization so manual recompress stays easy.
	masked_master.save(MACOS_DIR / "srxy.png", format="PNG", optimize=False)
	print(
		f"wrote {MACOS_DIR / 'srxy.png'} "
		f"({MASTER}x{MASTER}, {ART_SIZE} art + {MARGIN}px gutter)"
	)

	for size in SIZES:
		# Re-render per size so gutter/radius stay on-grid (avoid shrinking shadows badly).
		img = render_macos_icon(base, canvas_size=size)
		img.save(MACOS_DIR / f"srxy-{size}.png", format="PNG", optimize=False)
		print(f"wrote {MACOS_DIR / f'srxy-{size}.png'} ({size}x{size})")


if __name__ == "__main__":
	main()
