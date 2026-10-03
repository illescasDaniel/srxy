#!/usr/bin/env python3
"""Benchmark Unlimited OCR (baidu/Unlimited-OCR) vs Tesseract: quality + speed.

Usage:
    python scripts/bench_ocr_unlimited_vs_tesseract.py
    python scripts/bench_ocr_unlimited_vs_tesseract.py --iters 5

Gracefully skips backends that are not available:
  - The Tesseract scenario needs the `tesseract` binary on PATH.
  - The Unlimited OCR scenario needs `srxy[semantic]` (torch + transformers
    importable) *and* a cached baidu/Unlimited-OCR model — see
    `python -m srxy.adapters.outbound.models.model_store unlimited-ocr`.
    This script never triggers a model download or requires a GPU; it is
    meant to be re-run on GPU hardware for a real A/B once the model is
    cached (see memory/activeContext.md for the pending GPU QA).

Quality is a coarse proxy: the fraction of fixtures whose recognized text
contains at least one expected token (case-insensitive substring match). It
is not a full text-similarity/CER metric, but it is enough to catch
regressions between backends on the same fixture set used by the OCR
integration tests.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
from pathlib import Path
from statistics import mean


_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from PIL import Image  # noqa: E402

from srxy.adapters.outbound.models.model_store import (  # noqa: E402
	is_model_installed,
	unlimited_ocr_model_dir,
)
from srxy.adapters.outbound.ocr import ocr_text  # noqa: E402


FIXTURES_ROOT = _REPO / "tests" / "fixtures" / "file_search"
OCR_DIR = FIXTURES_ROOT / "ocr"

# (fixture path, expected substrings — any hit counts as a pass for that fixture)
FIXTURE_CASES: list[tuple[Path, tuple[str, ...]]] = [
	(FIXTURES_ROOT / "cover.jpg", ("fixture", "composer")),
	(OCR_DIR / "ocr_sample.png", ("revenue",)),
]
for _orientation_path in sorted((OCR_DIR / "orientation").glob("*.jpg")):
	_name = _orientation_path.stem.lower()
	if "sister" in _name:
		FIXTURE_CASES.append((_orientation_path, ("sister",)))
	elif "smoking" in _name:
		FIXTURE_CASES.append((_orientation_path, ("smoking",)))


def _require_fixtures():
	if not (OCR_DIR / "ocr_sample.png").is_file():
		print(
			f"ERROR: OCR fixtures not found under {OCR_DIR}\n"
			"       Expected tests/fixtures/file_search/ocr/ in the checkout.",
			file=sys.stderr,
		)
		sys.exit(1)


def _run_backend(name: str, iters: int) -> dict[str, float | int]:
	"""Force `name` ("tesseract" | "unlimited") for get_ocr_engine() and benchmark it."""
	original = ocr_text.is_unlimited_ocr_available
	ocr_text.reset_ocr_engine()
	ocr_text.is_unlimited_ocr_available = (lambda: True) if name == "unlimited" else (lambda: False)  # type: ignore[method-assign]
	durations: list[float] = []
	hits = 0
	try:
		for path, expected in FIXTURE_CASES:
			text = ""
			with Image.open(path) as image:
				image.load()
				for _ in range(iters):
					t0 = time.perf_counter()
					text = ocr_text.ocr_pil_image(image)
					durations.append(time.perf_counter() - t0)
			if any(token in text.lower() for token in expected):
				hits += 1
	finally:
		ocr_text.is_unlimited_ocr_available = original  # type: ignore[method-assign]
		ocr_text.reset_ocr_engine()

	total = len(FIXTURE_CASES)
	return {
		"hits": hits,
		"total": total,
		"quality": (hits / total) if total else 0.0,
		"mean_seconds": mean(durations) if durations else 0.0,
		"n_runs": len(durations),
	}


def _fmt_row(label: str, quality: str, speed: str) -> str:
	return f"  {label:<14}  {quality:<24}  {speed:<20}"


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--iters", type=int, default=1, help="OCR passes per fixture (default 1)")
	args = parser.parse_args()

	_require_fixtures()

	print(f"Platform     : {platform.system()} {platform.machine()}")
	print(f"Python       : {sys.version.split()[0]}")
	print(f"Fixtures     : {len(FIXTURE_CASES)} images under {OCR_DIR.parent}")
	print(f"Iterations   : {args.iters} pass(es) per fixture")
	print()

	results: dict[str, dict[str, float | int] | None] = {}

	if ocr_text.tesseract_available():
		results["tesseract"] = _run_backend("tesseract", args.iters)
	else:
		print("  [tesseract not on PATH — Tesseract scenario skipped]")
		results["tesseract"] = None

	unlimited_ready = ocr_text.unlimited_ocr_deps_installed() and is_model_installed(unlimited_ocr_model_dir())
	if unlimited_ready:
		results["unlimited"] = _run_backend("unlimited", args.iters)
	else:
		print(
			"  [Unlimited OCR skipped — needs srxy[semantic] (torch + transformers) and a cached "
			"baidu/Unlimited-OCR model; run "
			"`python -m srxy.adapters.outbound.models.model_store unlimited-ocr` on GPU hardware "
			"for a real A/B]"
		)
		results["unlimited"] = None

	print()
	print(_fmt_row("Backend", "Quality (hits/total)", "Mean time/fixture"))
	print("  " + "-" * 60)
	for name, data in results.items():
		if data is None:
			print(_fmt_row(name, "skipped", "—"))
			continue
		quality_str = f"{data['hits']}/{data['total']} ({data['quality']:.0%})"
		speed_str = f"{data['mean_seconds'] * 1000:.0f} ms"
		print(_fmt_row(name, quality_str, speed_str))

	print()
	print("Done.")


if __name__ == "__main__":
	main()
