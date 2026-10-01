# Active Context

_Last updated: 2026-10-01_

## Branch

- Topic branch `cursor/gui-dnd-path-field-27be` (PR #41 → `feature/1.8.0`).
- Synced with `origin/feature/1.8.0` (folder-name search #40 + Search button top-fixed #51).

## Current focus

1. **GUI drag-and-drop folder onto path field** (Trello [voZsdHYf](https://trello.com/c/voZsdHYf)) — merge + gate green; awaiting review/QA.

## Done this session

- Merged `origin/feature/1.8.0` into this branch (`06cc21c`).
- Fixed 4 hidden-folder unit/CLI fixtures that wrote `.git/config` (blocked in agent sandbox) to use `.secret/notes.txt` instead.
- `CI=true` quality gate `core,gui,tui` PASSED.

## Next steps

1. Team Lead review; QA drag-drop on Linux/macOS/Windows before merge into `feature/1.8.0`.
2. Remaining 1.8.0 drafts (Unlimited OCR #38, media preview #39) stay on their topic branches.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
