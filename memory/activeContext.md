# Active Context

_Last updated: 2026-10-01_

## Branch

- Release train **`feature/1.8.0`** (includes #40 folder-name, #51 Search top-fixed, #41 path DnD).
- This branch: `cursor/gui-recent-searches-cf28` — GUI recent searches + restore last path/query session. Synced with latest `origin/feature/1.8.0` (2026-10-01).

## Current focus

1. **GUI recent searches + restore last session** (this branch) — merge into `feature/1.8.0` after checks + CI green.
2. Remaining 1.8.0 drafts: Unlimited OCR #38, media preview #39.

## Next steps

1. Local quality gate → push → CI green → merge PR into `feature/1.8.0`.
2. Update local `feature/1.8.0` after merge.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
