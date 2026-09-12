# Active Context

_Last updated: 2026-09-12_

## Branch

- `develop` — post-v1.7.0 (shipped `main` @ `2c64f08`, 2026-09-11).
- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).

## Current focus

1. **Unlimited OCR** — draft PR #38 → `feature/1.8.0`; Daniel GPU QA before undraft.
2. **Media preview panel** — draft PR #39 → `feature/1.8.0`; Team Lead LGTM; Daniel visual/playback smoke before undraft.
3. **Search by folder name** — GUI + TUI + CLI; topic branch off `feature/1.8.0`; tests required; Team Lead marks ready-for-review when OK.

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Folder-name search — Srxy Developer implements (GUI/TUI/CLI + tests); PR into `feature/1.8.0`.
2. Unlimited OCR — Daniel GPU QA; keep draft until then.
3. Media preview — Daniel smoke; then undraft/merge into `feature/1.8.0`.
4. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.

## Sync note (2026-09-12)

- Synced `develop` (@ `0fcda8b`, includes signed/notarized v1.7.0 macOS installer work + `docs/images/gui-linux.png` regeneration) into `feature/1.8.0` via PR #52. v1.7.0 macOS installer distribution work is complete/shipped; no outstanding action here.
