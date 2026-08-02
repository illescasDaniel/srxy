from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version


def _print_version() -> int:
	try:
		print(version("srxy"))
	except PackageNotFoundError:
		print("srxy (unknown version)")
	return 0


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(prog="srxy-installer", description="Install or uninstall srxy.")
	parser.add_argument("--version", action="store_true", help="Print srxy version and exit.")
	# parse_known_args keeps Qt-style unknown flags; --help still exits via argparse.
	args, _unknown = parser.parse_known_args(argv)
	if args.version:
		return _print_version()
	from srxy.adapters.inbound.installer.app import run_installer

	return run_installer()


if __name__ == "__main__":
	sys.exit(main())
