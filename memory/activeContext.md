# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Applied `cursor/5648e20a` (persist + live filters validation) into parent. Merge `9b3256a`; follow-up theme guard `1604fd9`.

## Verified

- Ancestry: `cursor/5648e20a` is ancestor of HEAD.
- Composed with Settings menu (`reset_settings` + persist helpers both present).
- No conflict markers.
- Direct pytest: gui controller + qml load + settings persist = 90 passed.

## Next steps

1. Manual: Persist options/filters; Filters live OK disable; Settings menu.
2. `/delete-worktree-srxy` for `cursor/5648e20a` (`699q`) when ready.
3. `/delete-worktree-srxy` for `cursor/5852d6f1` (`0svx`) when ready.
