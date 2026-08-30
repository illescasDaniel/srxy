# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Fixed Reset All Settings: also restores factory options/filters and clears persist flags; quit no longer recreates `settings.json` when the file is gone and persist is off.

## Verified

- `checks.sh --quiet --fix` + verify PASSED.
- GUI controller reset test asserts session prefs cleared and file stays absent after shutdown.

## Next steps

1. Manual: Reset All Settings with Persist on — options/filters should snap to defaults immediately; quit must not recreate `settings.json`.
2. Manual: Persist options/filters; Filters live OK disable; Settings menu.
3. `/delete-worktree-srxy` for `cursor/5648e20a` (`699q`) when ready.
4. `/delete-worktree-srxy` for `cursor/5852d6f1` (`0svx`) when ready.
