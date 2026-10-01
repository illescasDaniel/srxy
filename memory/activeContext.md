# Active Context

_Last updated: 2026-10-01_

## Branch

- `feature/media-preview-panel` — CI quality still red after 28×28 fix (macOS/Windows ✓); pinTop test now uses parent-local y.

## Current focus

1. **Ship PR #39** — push local-y pinTop assertion fix; merge when CI green.
2. Unlimited OCR — not touched.

## Next steps

1. On CI green: squash-merge PR #39 into `feature/1.8.0`, then `git checkout feature/1.8.0 && git pull`.
2. `gh` keyring token invalid — re-auth needed to fetch Actions logs locally.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
