# Active Context

_Last updated: 2026-09-07_

## Branch

- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).

## Current focus

1. **Unlimited OCR** — draft PR #38 → `feature/1.8.0`; Daniel GPU QA before undraft.
2. **Media preview panel** — draft PR #39 → `feature/1.8.0`; Team Lead LGTM; Daniel visual/playback smoke before undraft.
3. **Search by folder name** — GUI + TUI + CLI; topic branch off `feature/1.8.0`; tests required; Team Lead marks ready-for-review when OK.
4. **GUI drag-and-drop folder onto path field** (Trello [voZsdHYf](https://trello.com/c/voZsdHYf)) — implemented on branch `cursor/gui-dnd-path-field-27be`, PR → `feature/1.8.0`; awaiting review/QA.

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Folder-name search — Srxy Developer implements (GUI/TUI/CLI + tests); PR into `feature/1.8.0`.
2. Unlimited OCR — Daniel GPU QA; keep draft until then.
3. Media preview — Daniel smoke; then undraft/merge into `feature/1.8.0`.
4. GUI drag-and-drop path field — Team Lead review; QA drag-drop on Linux/macOS/Windows before merge.
5. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
