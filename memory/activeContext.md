# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — main checkout; cold-start + splash applied from `cursor/d34ce3c1`.

## Current focus

None active — apply-worktree complete; gate clean.

## Done this session

- Applied worktree `o850` / `cursor/d34ce3c1` (cold-start + splash); resolved conflicts with search overlap / permission-denied / preview fonts; merge `940957e`; `checks-win` fix+verify PASSED.
- Updated `/apply-worktree` skill to auto-resolve merge conflicts.

## Next steps

1. Optional: faster splash experiments.
2. Final QA: Windows/macOS installers; release when green.
3. `/delete-worktree` for `o850` when finished with the isolated checkout.

## Key files

- GUI splash/cold-start under `src/srxy/adapters/inbound/gui/` + `application/search_*` / `startup_timing`
- `docs/gui.md#startup-splash`
