# Active Context

_Last updated: 2026-08-29_

## Branch

- Worktree `9x6r` / `cursor/943ab584` — quality-gate speedup merged with latest `feature/fixes_1.6.6` (1.7.0 / splash / cold-start / skills). Gate green.

## Current focus

None active.

## Done this session

- Committed faster quality gate (`09aac8d`).
- Merged `feature/fixes_1.6.6` (`43cab32`): kept `tests/isolation.py`, retargeted stubs to `model_store`, moved `test_gui_splash.py` into `tests/gui/`, unioned memory.
- `checks-win-quiet` PASSED (shell WARN only: missing shellcheck/shfmt).

## Next steps

1. Optional: push branch / open PR into `feature/fixes_1.6.6` when asked.
2. Optional: post-change timings vs `.gate-baseline/` on a clean tree.
