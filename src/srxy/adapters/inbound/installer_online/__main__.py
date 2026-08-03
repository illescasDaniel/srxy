"""CLI entry for the one-click online installer."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _print_version() -> int:
	try:
		print(version("srxy"))
	except PackageNotFoundError:
		print("srxy (unknown version)")
	return 0


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		prog="srxy-installer-online",
		description="Install srxy from PyPI (one-click online installer).",
	)
	parser.add_argument("--version", action="store_true", help="Print srxy version and exit.")
	parser.add_argument(
		"--no-browser",
		action="store_true",
		help="Do not open a browser (for bootstrap handoff).",
	)
	parser.add_argument(
		"--url-file",
		type=Path,
		default=None,
		help="Write the installer URL to this path when the server is ready.",
	)
	args = parser.parse_args(argv)
	if args.version:
		return _print_version()
	try:
		from srxy.adapters.inbound.installer_online.server import run_online_installer

		return run_online_installer(
			open_browser=not args.no_browser,
			url_file=args.url_file,
		)
	except Exception as exc:
		print(f"srxy-installer-online failed: {exc}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	sys.exit(main())
