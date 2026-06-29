#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		description="Build sanitized photoshop_xmp.jpg test fixture from a source PNG.",
	)
	parser.add_argument(
		"--source",
		type=Path,
		required=True,
		help="Source PNG with EXIF/XMP (e.g. ~/Downloads/sample1.png)",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=_repo_root() / "tests/fixtures/file_search/samples/images/photoshop_xmp.jpg",
		help="Destination JPEG path",
	)
	parser.add_argument("--max-dimension", type=int, default=256)
	parser.add_argument("--quality", type=int, default=75)
	args = parser.parse_args(argv)

	repo_root = _repo_root()
	sys.path.insert(0, str(repo_root))
	from tests.helpers import build_photoshop_xmp_jpeg_fixture

	source = args.source.expanduser()
	output = args.output if args.output.is_absolute() else repo_root / args.output
	build_photoshop_xmp_jpeg_fixture(
		source,
		output,
		max_dimension=args.max_dimension,
		quality=args.quality,
	)
	print(f"Wrote {output} ({output.stat().st_size} bytes)")
	return 0


if __name__ == "__main__":
	sys.exit(main())
