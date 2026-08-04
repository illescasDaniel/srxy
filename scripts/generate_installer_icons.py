#!/usr/bin/env python3
"""Generate srxy-installer icons: base app icon + gears badge overlay.

Source of truth (uncompressed original):

	assets/icons/srxy.png

Packaged outputs (compress these) land under ``src/srxy/resources/icons/``.

Run from the repo root:

	task generate-installer-icons
	# or: uv run python scripts/generate_installer_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "assets" / "icons" / "srxy.png"
ICON_DIR = ROOT / "src" / "srxy" / "resources" / "icons"
SIZES = [16, 32, 48, 64, 128, 256, 512]
MASTER = 1024


def gear_path(
	cx: float,
	cy: float,
	outer_r: float,
	teeth: int,
	tooth_depth: float,
	rotation_deg: float = 0.0,
) -> list[tuple[float, float]]:
	"""Approximate gear outline as polygon points."""
	pts: list[tuple[float, float]] = []
	rot = math.radians(rotation_deg)
	for i in range(teeth):
		a0 = rot + (2 * math.pi * i) / teeth
		a1 = rot + (2 * math.pi * (i + 0.35)) / teeth
		a2 = rot + (2 * math.pi * (i + 0.5)) / teeth
		a3 = rot + (2 * math.pi * (i + 0.85)) / teeth
		a4 = rot + (2 * math.pi * (i + 1.0)) / teeth
		r_tip = outer_r
		r_valley = outer_r - tooth_depth
		for a, r in ((a0, r_valley), (a1, r_tip), (a2, r_tip), (a3, r_valley), (a4, r_valley)):
			pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
	return pts


def draw_gear(
	draw: ImageDraw.ImageDraw,
	cx: float,
	cy: float,
	outer_r: float,
	*,
	teeth: int,
	fill: tuple[int, int, int, int],
	hub_fill: tuple[int, int, int, int],
	rotation_deg: float = 0.0,
):
	tooth_depth = outer_r * 0.22
	inner_r = outer_r * 0.62
	hub_r = outer_r * 0.28
	outline = gear_path(cx, cy, outer_r, teeth, tooth_depth, rotation_deg)
	draw.polygon(outline, fill=fill)
	draw.ellipse(
		(cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
		fill=fill,
	)
	draw.ellipse(
		(cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r),
		fill=hub_fill,
	)


def make_badge(size: int) -> Image.Image:
	"""Circular badge with two interlocking gears."""
	s = max(size * 4, 256)
	img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

	shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
	sd = ImageDraw.Draw(shadow)
	pad = int(s * 0.06)
	sd.ellipse(
		(pad, pad + int(s * 0.04), s - pad, s - pad + int(s * 0.04)),
		fill=(0, 0, 0, 70),
	)
	shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(2, s // 40)))
	img = Image.alpha_composite(img, shadow)
	draw = ImageDraw.Draw(img)

	margin = int(s * 0.08)
	draw.ellipse(
		(margin, margin, s - margin, s - margin),
		fill=(245, 246, 248, 255),
		outline=(210, 214, 220, 255),
		width=max(1, s // 64),
	)

	charcoal = (45, 52, 58, 255)
	hub = (245, 246, 248, 255)
	draw_gear(
		draw,
		s * 0.42,
		s * 0.46,
		s * 0.28,
		teeth=8,
		fill=charcoal,
		hub_fill=hub,
		rotation_deg=12,
	)
	draw_gear(
		draw,
		s * 0.62,
		s * 0.58,
		s * 0.20,
		teeth=7,
		fill=charcoal,
		hub_fill=hub,
		rotation_deg=-8,
	)
	return img.resize((size, size), Image.Resampling.LANCZOS)


def composite(base: Image.Image) -> Image.Image:
	out = base.convert("RGBA").copy()
	w, h = out.size
	badge_size = max(8, int(round(w * 0.34)))
	if w <= 16:
		badge_size = max(6, int(round(w * 0.42)))
	badge = make_badge(badge_size)
	inset = max(1, int(round(w * 0.04)))
	x = inset
	y = h - badge_size - inset
	out.alpha_composite(badge, (x, y))
	return out


def main():
	if not ORIGINAL.is_file():
		raise SystemExit(f"missing original icon: {ORIGINAL}")
	master = Image.open(ORIGINAL).convert("RGBA")
	if master.size != (MASTER, MASTER):
		raise SystemExit(f"expected {MASTER}x{MASTER} master icon, got {master.size}")

	ICON_DIR.mkdir(parents=True, exist_ok=True)
	# Refresh packaged square masters from the uncompressed original.
	master.save(ICON_DIR / "srxy.png", format="PNG", optimize=False)
	print(f"wrote {ICON_DIR / 'srxy.png'} ({MASTER}x{MASTER})")
	for size in SIZES:
		sized = master.resize((size, size), Image.Resampling.LANCZOS)
		sized.save(ICON_DIR / f"srxy-{size}.png", format="PNG", optimize=False)
		print(f"wrote srxy-{size}.png ({size}x{size})")

	inst_master = composite(master)
	inst_master.save(ICON_DIR / "srxy-installer.png", format="PNG", optimize=False)

	for size in SIZES:
		if size >= 128:
			img = inst_master.resize((size, size), Image.Resampling.LANCZOS)
		else:
			img = composite(Image.open(ICON_DIR / f"srxy-{size}.png"))
		img.save(ICON_DIR / f"srxy-installer-{size}.png", format="PNG", optimize=False)
		print(f"wrote srxy-installer-{size}.png ({size}x{size})")
	print(f"wrote {ICON_DIR / 'srxy-installer.png'} ({MASTER}x{MASTER})")


if __name__ == "__main__":
	main()
