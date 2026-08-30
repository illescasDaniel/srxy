# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Applied from worktree `cursor/5648e20a`: **GUI persist options/filters** + **live filters validation**. Parent already has Settings menu maintenance from `cursor/5852d6f1`.

## Done (this apply)

- Persist options/filters via `settings.json` (OK + shutdown; restore without pre-probe clamp wipe)
- Live filters dialog validation (disable OK while invalid)
- Kept parent `reset_settings` / Settings menu APIs alongside persist helpers

## Next steps

1. Finish merge quality gate on parent.
2. Manual: Persist + Similar meaning; Filters live validation; Settings menu shortcuts.
3. `/delete-worktree-srxy` for `cursor/5648e20a` (`699q`) and `cursor/5852d6f1` (`0svx`) when ready.
