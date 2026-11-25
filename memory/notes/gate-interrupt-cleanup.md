---
name: gate-interrupt-cleanup
description: Track background PIDs in lib.sh with INT/TERM/EXIT traps that recursively kill process trees (pgrep + group kill). Apply in checks.sh (parallel light…
type: decision
date: 2026-09-11
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Cancelling `checks.sh` / `checks-win.ps1` with Ctrl+C left parallel pytest bucket subprocesses and lock holders running (orphan bash/pytest/xdist trees).
- **Decision:** Track background PIDs in `lib.sh` with INT/TERM/EXIT traps that recursively kill process trees (`pgrep` + group kill). Apply in `checks.sh` (parallel light steps + pytest subshell), `pytest.sh` (concurrent buckets), and `run_with_watch.sh` (setsid pytest leader). Windows: register `Start-Process` children, handle `[Console]::CancelKeyPress`, and `Stop-ProcessTree` / `taskkill /T` in `finally` blocks.
- **Rationale:** Ctrl+C should tear down the whole gate, not just the foreground `wait`. Verified scoped gate PASSED after changes.
