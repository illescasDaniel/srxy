# Active Context

_Last updated: 2026-09-07_

## Branch

- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).
- This branch: `cursor/gui-recent-searches-cf28` — GUI recent searches + restore last path/query session (Trello card, scope locked 2026-09-07).

## Current focus

1. **GUI recent searches + restore last session** (this branch) — last successful search (path/query text/query mode only, no filters) persisted to `settings.json` `recent_searches` (cap 20, newest first); launch Restore/Dismiss banner (never auto-starts search); query-field chevron popover with Restore / Restore & Search / Clear all. Reset preferences clears history too. Unit + GUI tests added; PR into `feature/1.8.0`.
2. **Unlimited OCR** — draft PR #38 → `feature/1.8.0`; Daniel GPU QA before undraft.
3. **Media preview panel** — draft PR #39 → `feature/1.8.0`; Team Lead LGTM; Daniel visual/playback smoke before undraft.
4. **Search by folder name** — GUI + TUI + CLI; topic branch off `feature/1.8.0`; tests required; Team Lead marks ready-for-review when OK.

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Folder-name search — Srxy Developer implements (GUI/TUI/CLI + tests); PR into `feature/1.8.0`.
2. Unlimited OCR — Daniel GPU QA; keep draft until then.
3. Media preview — Daniel smoke; then undraft/merge into `feature/1.8.0`.
4. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
