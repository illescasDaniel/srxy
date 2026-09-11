"""Lossy PNG compression via pngquant (pngquant-cli dev dependency)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PNGQUANT_QUALITY = 40


def compress_png(path: Path, *, quality: int = PNGQUANT_QUALITY):
	"""Quantize a PNG in place."""
	pngquant = shutil.which("pngquant")
	if pngquant is None:
		raise SystemExit(
			"pngquant not found on PATH; run `uv run task sync-dev` (pngquant-cli is a dev dependency)"
		)
	result = subprocess.run(
		[
			pngquant,
			f"--quality={quality}-{quality}",
			"--force",
			"--ext",
			".png",
			str(path),
		],
		capture_output=True,
		text=True,
	)
	if result.returncode != 0:
		detail = (result.stderr or result.stdout or "").strip()
		raise SystemExit(f"pngquant failed for {path}: {detail or result.returncode}")
