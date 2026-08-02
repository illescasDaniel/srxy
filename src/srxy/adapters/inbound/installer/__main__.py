from __future__ import annotations

import sys

from srxy.adapters.inbound.installer.app import run_installer


def main() -> int:
	return run_installer()


if __name__ == "__main__":
	sys.exit(main())
