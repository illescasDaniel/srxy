---
name: single-taskipy-checks-task
description: Replace the matrix with one Taskipy task (python scripts/quality/checks.py) that detects the OS and forwards documented flags (--fix, --full, --full+cpu…
type: decision
date: 2026-09-11
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** The quality gate had ~34 Taskipy entries (`checks`, `checks-win`, `*-quiet`, scoped variants) duplicating the same flag combinations across Unix and Windows.
- **Decision:** Replace the matrix with one Taskipy task (`python scripts/quality/checks.py`) that detects the OS and forwards documented flags (`--fix`, `--full`, `--full+cpu`, `--quiet`, `--scope`, bucket shorthands) to `checks.sh` or `checks-win.ps1`. Pass flags after `--` in Taskipy so `uv run` does not consume `--quiet`. Keep verbose as the default; agents pass `--quiet` explicitly. CI still invokes `checks.sh` directly.
- **Rationale:** One discoverable entry point with `--help`; same flags on every OS; removes Windows/Unix task naming drift. Verified: unit tests for dispatch, `uv run task checks -- --help`, scoped gate `uv run task checks -- --quiet --scope=core,gui,tui` PASSED.
