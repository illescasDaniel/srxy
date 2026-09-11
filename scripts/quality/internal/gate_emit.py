#!/usr/bin/env python3
"""Emit GitHub Actions workflow commands and summary counts for the quality gate."""

from __future__ import annotations

import sys
from typing import TextIO


def _print_summary(errors: int, warnings: int):
	print(f"GATE_SUMMARY errors={errors} warnings={warnings}", file=sys.stderr)


def cmd_github_annotations(stdin: TextIO | None = None) -> int:
	"""Count and forward GitHub Actions annotation lines (::error / ::warning)."""
	src = stdin or sys.stdin
	errors = 0
	warnings = 0
	for raw_line in src:
		line = raw_line.rstrip("\n")
		if not line:
			continue
		print(line)
		if line.startswith("::error"):
			errors += 1
		elif line.startswith("::warning"):
			warnings += 1
	_print_summary(errors, warnings)
	return 1 if errors else 0


def main() -> int:
	if len(sys.argv) < 2:
		print("usage: gate_emit.py {ty|ruff-github|github}", file=sys.stderr)
		return 2
	command = sys.argv[1]
	match command:
		case "ty" | "ruff-github" | "github":
			return cmd_github_annotations()
		case _:
			print(f"unknown command: {command}", file=sys.stderr)
			return 2


if __name__ == "__main__":
	sys.exit(main())
