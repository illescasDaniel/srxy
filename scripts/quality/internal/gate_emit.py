#!/usr/bin/env python3
"""Emit GitHub Actions workflow commands and summary counts for the quality gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO


def _repo_relative(path: str) -> str:
	p = Path(path)
	if p.is_absolute():
		try:
			return str(p.relative_to(Path.cwd()))
		except ValueError:
			return str(p)
	return str(p)


def _emit_error(
	out: TextIO,
	message: str,
	*,
	file: str = "",
	line: int = 0,
	col: int = 0,
	title: str = "quality-gate",
):
	if file and line:
		if col:
			out.write(f"::error file={file},line={line},col={col},title={title}::{message}\n")
		else:
			out.write(f"::error file={file},line={line},title={title}::{message}\n")
	else:
		out.write(f"::error title={title}::{message}\n")


def _emit_warning(
	out: TextIO,
	message: str,
	*,
	file: str = "",
	line: int = 0,
	col: int = 0,
	title: str = "quality-gate",
):
	if file and line:
		if col:
			out.write(f"::warning file={file},line={line},col={col},title={title}::{message}\n")
		else:
			out.write(f"::warning file={file},line={line},title={title}::{message}\n")
	else:
		out.write(f"::warning title={title}::{message}\n")


def _print_summary(errors: int, warnings: int):
	print(f"GATE_SUMMARY errors={errors} warnings={warnings}", file=sys.stderr)


def cmd_pyright(stdin: TextIO | None = None) -> int:
	src = stdin or sys.stdin
	errors = 0
	warnings = 0
	try:
		payload = json.load(src)
	except json.JSONDecodeError:
		_emit_error(sys.stdout, "basedpyright returned invalid JSON")
		_print_summary(1, 0)
		return 1
	for diag in payload.get("generalDiagnostics", []):
		severity = str(diag.get("severity", "error")).lower()
		message = str(diag.get("message", "diagnostic"))
		file_path = _repo_relative(str(diag.get("file", "")))
		range_info = diag.get("range") or {}
		start = range_info.get("start") or {}
		line = int(start.get("line", 0)) + 1
		col = int(start.get("character", 0)) + 1
		rule = diag.get("rule")
		title = f"basedpyright ({rule})" if rule else "basedpyright"
		if severity == "error":
			errors += 1
			_emit_error(sys.stdout, message, file=file_path, line=line, col=col, title=title)
		else:
			warnings += 1
			_emit_warning(sys.stdout, message, file=file_path, line=line, col=col, title=title)
	summary = payload.get("summary") or {}
	errors = max(errors, int(summary.get("errorCount", 0)))
	warnings = max(
		warnings,
		int(summary.get("warningCount", 0)) + int(summary.get("informationCount", 0)),
	)
	_print_summary(errors, warnings)
	return 1 if errors else 0


def cmd_ruff_github(stdin: TextIO | None = None) -> int:
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
		print("usage: gate_emit.py {pyright|ruff-github}", file=sys.stderr)
		return 2
	command = sys.argv[1]
	match command:
		case "pyright":
			return cmd_pyright()
		case "ruff-github":
			return cmd_ruff_github()
		case _:
			print(f"unknown command: {command}", file=sys.stderr)
			return 2


if __name__ == "__main__":
	sys.exit(main())
