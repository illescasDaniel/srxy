# Active Context

_Last updated: 2026-08-29_

## Branch

- Worktree `9x6r` / `cursor/943ab584` — quality-gate speedup + merge from `feature/fixes_1.6.6` (1.7.0 / splash / cold-start / skills).

## Current focus

Finish merge conflict resolution and verify the quiet gate.

## Done this session

- Committed faster quality gate (`09aac8d`).
- Merging `feature/fixes_1.6.6` (version 1.7.0, splash, cold-start, preview fonts, worktree skills).
- Kept shared `tests/isolation.py`; retargeted model stubs to `model_store` after cold-start move.

## Next steps

1. Complete merge commit after resolving memory + conftest conflicts.
2. Run `checks-win-quiet` (or scoped quiet gate) and fix any post-merge fallout.
