---
name: quality-gate-path-buckets
description: (1) Path-based pytest buckets (core/gui/tui/heavy) as separate processes, longest-job-first, overlapping light steps. (2) Auto-scope from git diff/status…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Day-to-day `checks` was slow on Windows: every pytest process imported PySide6 via pytest-qt; the "safe" pass still collected Qt/Textual `unit` files; the heavy serial pass (~123 tests / ~4:44) had no change-awareness; Windows light steps ran sequentially and pytest stdout was piped per-line through PowerShell.
- **Decision:** (1) Path-based pytest buckets (`core`/`gui`/`tui`/`heavy`) as separate processes, longest-job-first, overlapping light steps. (2) Auto-scope from `git diff`/`status` with `--scope`/`--gui`/`--tui`/`--all` overrides; `--full` ⇒ all. (3) Move Qt/Textual/real-backend tests under `tests/gui|tui|integration`; shared isolation in `tests/isolation.py` (not root conftest). (4) `-p no:pytest-qt` everywhere except `gui`; per-bucket testmon via `TESTMON_DATAFILE`; `.gate-cache` for pip-audit/build. (5) Windows: parallel light steps via `Start-Process` (not `Start-Job`), inherited pytest stdout, targeted shell-script walk, direct `.venv\Scripts` exes, wall watchdog, `checks-win.cmd` prefers `pwsh`.
- **Rationale:** Marker deselection happens after import, so only path selection removes Qt/torch cost from workers. Process-level buckets avoid the historical xdist shared-state mess while still overlapping wall clock. Auto-scope keeps the default correct rather than merely fast.
