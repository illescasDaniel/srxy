#!/usr/bin/env python3
"""Structural checks for an SDD SPEC.md (standard library only, any project language).

Checks what an agent or reviewer would otherwise eyeball: Metadata exists and its
wireframe links resolve, all four design decisions are answered (a bare ``N/A``
needs a reason), every ``### Scenario:`` has Given/When/Then, and Out of scope
exists. Whether the code satisfies the spec stays a judgement call for the grader.

Exit code 1 when any hard ``FAIL`` is found; ``WARN`` lines never change it.

	python3 spec_check.py specs/<feature>/SPEC.md [more specs…] [--root <repo>]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DESIGN_DECISION_KEYS = ("success criteria", "failure handling", "performance", "trust boundary")


@dataclass
class Report:
	"""Accumulates check results; ``fails`` decide the exit code."""

	lines: list[str] = field(default_factory=list)
	fails: int = 0

	def ok(self, message: str) -> None:
		self.lines.append(f"PASS  {message}")

	def fail(self, message: str) -> None:
		self.fails += 1
		self.lines.append(f"FAIL  {message}")

	def warn(self, message: str) -> None:
		self.lines.append(f"WARN  {message}")


def _section(text: str, heading: str) -> str | None:
	match = re.search(
		rf"^##\s+{re.escape(heading)}\b.*?$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL | re.IGNORECASE
	)
	return match.group(1) if match else None


def _design_decision_problems(section: str) -> list[str]:
	"""Each decision must appear and carry real content; a bare ``N/A`` needs a reason."""
	lines = section.lower().splitlines()
	starts = {key: next((i for i, line in enumerate(lines) if key in line), None) for key in DESIGN_DECISION_KEYS}
	ordered = sorted(i for i in starts.values() if i is not None)
	problems = []
	for key, start in starts.items():
		if start is None:
			problems.append(f"'{key}' missing")
			continue
		end = next((i for i in ordered if i > start), len(lines))
		chunk = " ".join(lines[start:end])
		content = re.sub(r"[^a-z0-9]+", "", chunk.split(key, 1)[1])
		if len(content) < 15 or ("n/a" in chunk and len(content.replace("na", "", 1)) < 12):
			problems.append(f"'{key}' empty or bare N/A")
	return problems


def check_spec(root: Path, spec: Path, report: Report) -> None:
	"""Structure of one SPEC.md."""
	text = spec.read_text(encoding="utf-8")
	rel = spec.resolve().relative_to(root) if spec.resolve().is_relative_to(root) else spec

	metadata = _section(text, "Metadata")
	if metadata is None:
		report.fail(f"{rel}: missing ## Metadata")
	else:
		wireframes = re.findall(r"wireframes/[\w./#-]+?\.html", metadata)
		missing = [w for w in wireframes if not (root / w).is_file()]
		if not wireframes:
			report.warn(f"{rel}: Metadata links no wireframes/*.html")
		elif missing:
			report.fail(f"{rel}: linked wireframe(s) not found: {', '.join(missing)}")
		else:
			report.ok(f"{rel}: linked wireframe(s) exist")

	decisions = _section(text, "Design decisions")
	if decisions is None:
		report.fail(
			f"{rel}: missing ## Design decisions (success criteria, failure handling, performance, trust boundary)"
		)
	else:
		problems = _design_decision_problems(decisions)
		if problems:
			report.fail(f"{rel}: Design decisions incomplete: {'; '.join(problems)}")
		else:
			report.ok(f"{rel}: all four design decisions answered")

	if _section(text, "Out of scope") is None:
		report.warn(f"{rel}: missing ## Out of scope")

	scenarios = re.findall(r"^###\s+Scenario:\s*(.+?)\s*$", text, re.MULTILINE)
	if not scenarios:
		report.fail(f"{rel}: no '### Scenario:' headings found")
		return
	incomplete = []
	for block in re.split(r"^###\s+Scenario:", text, flags=re.MULTILINE)[1:]:
		title = block.splitlines()[0].strip()
		if not all(re.search(rf"\*\*{kw}\*\*", block) for kw in ("Given", "When", "Then")):
			incomplete.append(title)
	if incomplete:
		report.fail(f"{rel}: {len(incomplete)} scenario(s) lack **Given** / **When** / **Then**")
		report.lines.extend(f"        {t}" for t in incomplete)
	else:
		report.ok(f"{rel}: {len(scenarios)} scenario(s), each with Given/When/Then")


def _default_root() -> Path:
	try:
		result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
	except OSError:
		return Path.cwd()
	return Path(result.stdout.strip()) if result.returncode == 0 else Path.cwd()


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Structural checks for SDD SPEC.md files")
	parser.add_argument("specs", nargs="+", type=Path, help="SPEC.md file(s) to check")
	parser.add_argument("--root", type=Path, help="repo root for wireframe links (default: git toplevel or cwd)")
	args = parser.parse_args(argv)

	root = (args.root or _default_root()).resolve()
	report = Report()
	for spec in args.specs:
		if not spec.is_file():
			report.fail(f"{spec}: file not found")
			continue
		check_spec(root, spec, report)
	print("\n".join(report.lines))
	print(f"\n{'FAILED' if report.fails else 'OK'}: {report.fails} hard failure(s)")
	return 1 if report.fails else 0


if __name__ == "__main__":
	sys.exit(main())
