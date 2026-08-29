# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — applying GUI cold-start + splash from worktree `cursor/d34ce3c1`.

## Current focus

Finish apply-worktree: merge conflicts resolved; quality gate then merge commit.

## Done this session

- Merged worktree cold-start + splash into parent (compose with search overlap / permission-denied / preview font fixes).
- Updated `/apply-worktree` skill to auto-resolve merge conflicts.

## Next steps

1. `checks-win-fix-quiet` → `checks-win-quiet` on main checkout.
2. Complete merge commit if not already done.
3. Optional: faster splash; Final QA installers; `/delete-worktree` for `o850` when done.

## Key files

- `src/srxy/adapters/inbound/gui/{app.py,splash.py,qml/Splash.qml}`
- `src/srxy/application/{search_defaults,skipped_file_warnings,startup_timing}.py`
- `docs/gui.md` (Startup splash)
