# Active Context

_Last updated: 2026-10-01_

## Branch

- Release train **`feature/1.8.0`**.
- This branch: `cursor/gui-recent-searches-cf28` — synced with `origin/feature/1.8.0`, local gate green, pushed `60f3c37`. PR #42 undrafted; waiting on CI then squash-merge into `feature/1.8.0`.

## Current focus

1. **Wait for CI on PR #42** → merge when green → update local `feature/1.8.0`.

## Next steps

1. On CI green: squash-merge PR #42.
2. `git checkout feature/1.8.0 && git pull` (or merge origin) to refresh local train.
3. Remaining drafts: Unlimited OCR #38, media preview #39.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
