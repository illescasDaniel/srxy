---
name: taskipy-gate-tasks-verbose-default
description: Reverted checks/checks-fix/checks-win/checks-win-fix to plain (verbose) commands. Added explicit -quiet variants for every gate mode on both platforms…
type: decision
date: 2026-08-19
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** The first iteration made the day-to-day Taskipy tasks (`checks`/`checks-fix`/`checks-win`/`checks-win-fix`) default to `--quiet`. The user preferred humans keep the verbose default and agents opt into quiet explicitly.
- **Decision:** Reverted `checks`/`checks-fix`/`checks-win`/`checks-win-fix` to plain (verbose) commands. Added explicit `*-quiet` variants for every gate mode on both platforms: `checks-quiet`, `checks-fix-quiet`, `checks-full-quiet`, `checks-full-cpu-quiet`, `checks-win-quiet`, `checks-win-fix-quiet`, `checks-win-full-quiet`, `checks-win-full-cpu-quiet`. `AGENTS.md` instructs AI agents to always use the quiet variants (direct `--quiet`/`-Quiet` flags or `*-quiet` tasks); the release line points agents at `checks-full-quiet` / `checks-full-cpu-quiet`.
- **Rationale:** Keeps the human-facing day-to-day commands unchanged (no silent behavior change) while giving agents an explicit, discoverable low-token path. Verified with `uv run task checks` (verbose, PASSED) and `uv run task checks-quiet` (quiet, PASSED).
