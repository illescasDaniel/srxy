# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Faster quality gate applied from worktree `9x6r` / `cursor/943ab584`.

## Current focus

Finish apply-worktree quality gate on this checkout; then optional `/delete-worktree-srxy` for `9x6r` (and leftover `hsfl` if still present).

## Done this session

- Applied worktree `hsfl` / `cursor/5e55b1ae` (`c543b19`): project skills.
- Applied worktree `9x6r` / `cursor/943ab584` (`20e751c`): path-bucket quality gate, auto-scope, Windows parallelization, test reorg.

## Next steps

1. Quality gate on main checkout (`checks-win-fix-quiet` then `checks-win-quiet`).
2. `/delete-worktree-srxy` for applied worktrees when ready.
3. Final QA / release for 1.7.0 when ready.
