# Active Context

_Last updated: 2026-09-06_

## Branch

- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).

## Current focus

1. **Unlimited OCR** — draft PR #38 → `feature/1.8.0`; Daniel GPU QA before undraft.
2. **Media preview panel** — draft PR #39 → `feature/1.8.0`; Team Lead LGTM; Daniel visual/playback smoke before undraft.
3. **Search by folder name** — implemented on `cursor/search-by-folder-name-b203` (topic branch off `feature/1.8.0`); PR opened → `feature/1.8.0`; unit + CLI + TUI + GUI tests added, docs + i18n updated. Team Lead marks ready-for-review when OK. Do not touch `feature/unlimited-ocr-dca2` (#38) or `feature/media-preview-panel` (#39).

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Folder-name search — PR review; see `memory/decisions.md` (2026-09-06) for the true-folder-as-result design; regenerated the 4 TUI snapshots that show the changed "File names" hint copy.
2. Unlimited OCR — Daniel GPU QA; keep draft until then.
3. Media preview — Daniel smoke; then undraft/merge into `feature/1.8.0`.
4. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
