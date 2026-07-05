#!/usr/bin/env python3
"""Benchmark magic_file_search against the integration fixtures.

Usage:
    python scripts/bench_file_search.py
    python scripts/bench_file_search.py --cold       # cold cache (no warm-up)
    python scripts/bench_file_search.py --iters 5    # more iterations for stability

Scenarios measured:
  1. Text-only search   — exercises exact/fuzzy/phonetic matching
  2. Document search    — exercises docx/xlsx/pptx parsing
  3. OCR search         — exercises tesseract; highest parallelism benefit
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from pathlib import Path
from statistics import mean, stdev


_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

from srxy.cache import reset_cache_connection, reset_run_file_hashes
from srxy.file_search import magic_file_search
from srxy.ocr_text import tesseract_available


FIXTURES_ROOT = _REPO / "tests" / "fixtures" / "file_search"
DEFAULT_ITERS = 3


def _require_fixtures() -> Path:
	marker = FIXTURES_ROOT / "notes.txt"
	if not marker.is_file():
		print(
			f"ERROR: fixtures not found at {FIXTURES_ROOT}\n"
			"       Expected tests/fixtures/file_search/ in the checkout.",
			file=sys.stderr,
		)
		sys.exit(1)
	return FIXTURES_ROOT


def _reset_state(cold: bool):
	reset_run_file_hashes()
	reset_cache_connection()
	if cold:
		# Drop all SQLite cache entries so OCR/document parsing actually re-runs.
		# We intentionally do NOT reset the semantic model — that load would dominate
		# the timing and is not what we are measuring here.
		from srxy.cache import cache_db_path

		db = cache_db_path()
		if db.is_file():
			import sqlite3

			with sqlite3.connect(db) as conn:
				conn.execute("DELETE FROM cache_entries")
				conn.commit()


def _bench(root: Path, query: str, iters: int, cold: bool, **kwargs: object) -> tuple[list[float], int]:
	# one untimed warm-up (semantic model load + first OCR when warm-cache)
	_reset_state(cold=False)
	magic_file_search(root, query, **kwargs)  # type: ignore[arg-type]

	times: list[float] = []
	n_results = 0
	for i in range(iters):
		_reset_state(cold)
		t0 = time.perf_counter()
		results = magic_file_search(root, query, **kwargs)  # type: ignore[arg-type]
		times.append(time.perf_counter() - t0)
		if i == 0:
			n_results = len(results)
	return times, n_results


def _fmt_times(times: list[float]) -> str:
	if len(times) == 1:
		return f"{times[0] * 1000:.0f} ms"
	avg = mean(times) * 1000
	lo = min(times) * 1000
	hi = max(times) * 1000
	sd = stdev(times) * 1000
	return f"{avg:.0f} ms  (min {lo:.0f} / max {hi:.0f} / σ {sd:.0f})"


def _file_count(root: Path) -> int:
	return sum(1 for p in root.rglob("*") if p.is_file())


def main():
	parser = argparse.ArgumentParser(
		description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("--cold", action="store_true", help="Cold cache (reset state between each run)")
	parser.add_argument("--iters", type=int, default=DEFAULT_ITERS, help=f"Iterations per scenario (default {DEFAULT_ITERS})")
	parser.add_argument("--label", default="", help="Optional label to prefix in the header (e.g. 'baseline' or 'threaded')")
	args = parser.parse_args()

	root = _require_fixtures()

	os.environ.setdefault("SRXY_SEMANTIC", "1")
	os.environ.setdefault("SRXY_AUTO_DOWNLOAD", "1")

	cpu_count = os.cpu_count() or 1
	print(f"Label        : {args.label or '(none)'}")
	print(f"Platform     : {platform.system()} {platform.machine()}")
	print(f"Python       : {sys.version.split()[0]}")
	print(f"CPU cores    : {cpu_count}")
	print(f"Fixture root : {root}")
	print(f"File count   : {_file_count(root)}")
	print(f"Iterations   : {args.iters}")
	print(f"Cache mode   : {'cold' if args.cold else 'warm'}")
	print()

	# (label, search_root_relative_to_fixtures, query, kwargs)
	scenarios: list[tuple[str, Path, str, dict[str, object]]] = [
		(
			"Text — full tree",
			root,
			"axolotl",
			{"search_names": False},
		),
		(
			"Text — documents folder",
			root / "samples" / "documents",
			"fixture_docx_token",
			{"search_names": False},
		),
	]
	if tesseract_available():
		scenarios += [
			(
				"OCR — ocr/ folder",
				root / "ocr",
				"revenue",
				{"search_names": False, "ocr": True},
			),
			(
				"OCR — samples/ocr/ folder",
				root / "samples" / "ocr",
				"fixture_ocr_token",
				{"search_names": False, "ocr": True},
			),
		]
	else:
		print("  [tesseract not available — OCR scenarios skipped]")

	col_label = 36
	col_time = 38
	col_n = 7
	header = f"  {'Scenario':<{col_label}}  {'Time (mean, min/max/σ)':<{col_time}}  {'N':>{col_n}}"
	print(header)
	print("  " + "-" * (col_label + col_time + col_n + 4))

	for label, search_root, query, kwargs in scenarios:
		times, n = _bench(search_root, query, args.iters, args.cold, **kwargs)
		time_str = _fmt_times(times)
		print(f"  {label:<{col_label}}  {time_str:<{col_time}}  {n:>{col_n}}")

	print()
	print("Done.")


if __name__ == "__main__":
	main()
