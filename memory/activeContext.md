# Active Context

_Last updated: 2026-10-01_

## Branch

- `feature/media-preview-panel` (off `feature/1.8.0`) — media preview polish after merging latest `feature/1.8.0` (folder-name search, Search top-fixed, path DnD, recent searches).

## Current focus

1. **Media preview polish** — silence `qt.multimedia.ffmpeg` FFmpeg LGPL info log; show a video poster/thumbnail in the preview panel; replace play/pause (and mute) text with proper icons.
2. **Unlimited OCR** (draft PR #38 → `feature/1.8.0`) — stay draft until Daniel GPU QA. **Not touched by this session.**

## Next steps

1. Finish media preview polish (FFmpeg log / video thumbnail / play-pause icons), gate, then hand off for visual smoke before undrafting PR #39.
2. Unlimited OCR — Daniel GPU QA; keep draft (separate branch/PR).
3. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
