# Active Context

_Last updated: 2026-10-01_

## Branch

- `feature/media-preview-panel` (off `feature/1.8.0`) — media preview + polish; merge of latest `feature/1.8.0` done (`d2cd258`).

## Current focus

1. **Media preview polish — done this session** (uncommitted): FFmpeg Qt log silence, video poster thumbnail, play/pause/mute icons. Gate `core,gui` PASSED.
2. **Unlimited OCR** (draft PR #38) — not touched.

## Next steps

1. Commit polish when asked; visual smoke on macOS (video poster + icons); undraft PR #39 when Daniel ready.
2. Unlimited OCR — Daniel GPU QA (separate branch).
3. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
