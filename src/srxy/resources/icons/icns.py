"""Build macOS ``.icns`` without relying on ``iconutil -c`` (broken on macOS 26+)."""

from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

from PIL import Image


def write_icns_from_png(icon_png: Path, icns_path: Path):
	"""Write a multi-resolution ``.icns`` from a square PNG.

	macOS 26+ ``iconutil -c icns`` rejects iconsets that older releases accepted
	(``Invalid Iconset``). Pack modern PNG-backed ICNS chunks ourselves instead;
	``iconutil --convert iconset`` can still round-trip the result.
	"""
	image = Image.open(icon_png).convert("RGBA")
	# OSType → pixel edge. Covers 1x and @2x slots Finder/Dock expect.
	sizes: tuple[tuple[bytes, int], ...] = (
		(b"icp4", 16),
		(b"ic11", 32),
		(b"icp5", 32),
		(b"ic12", 64),
		(b"ic07", 128),
		(b"ic13", 256),
		(b"ic08", 256),
		(b"ic14", 512),
		(b"ic09", 512),
		(b"ic10", 1024),
	)
	chunks: list[bytes] = []
	for ostype, edge in sizes:
		buf = BytesIO()
		image.resize((edge, edge), Image.Resampling.LANCZOS).save(buf, format="PNG")
		payload = buf.getvalue()
		chunks.append(ostype + struct.pack(">I", 8 + len(payload)) + payload)
	body = b"".join(chunks)
	icns_path.parent.mkdir(parents=True, exist_ok=True)
	icns_path.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + body)


__all__ = ["write_icns_from_png"]
