---
name: gate-lock-file-pids
description: While the gate runs, write key=value metadata to the lock file: pid, pids (main + tracked children), started, script, status (running/exited/interrupted)…
type: decision
date: 2026-09-11
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** When the gate refused a second run, `.srxy-quality-gate.lock` was empty — no hint which process held the flock / exclusive file lock.
- **Decision:** While the gate runs, write key=value metadata to the lock file: `pid`, `pids` (main + tracked children), `started`, `script`, `status` (`running`/`exited`/`interrupted`), `updated`. On lock contention, print the file plus a per-PID alive check (`kill -0` / `Get-Process`). Unix updates via `lib.sh`; Windows writes through the held `LockStream`.
- **Rationale:** Makes stale-lock diagnosis actionable (`kill <pid>`) without spelunking `pgrep`. Tests: `tests/unit/test_gate_lock_file.py`.
