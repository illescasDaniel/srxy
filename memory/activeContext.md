# Active Context

_Last updated: 2026-10-01_

## Branch

- `feature/media-preview-panel` — CI quality red on pinTop layout drift from chevron ToolButton sizing; restoring flat 28×28, re-push.

## Current focus

1. **Ship PR #39** — fix Search pinTop regression from chevron change, then merge when CI green.
2. Unlimited OCR — not touched.

## Next steps

1. Push fix; on CI green squash-merge PR #39; pull `feature/1.8.0` locally.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
