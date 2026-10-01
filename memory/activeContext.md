# Active Context

_Last updated: 2026-10-01_

## Branch

- `cursor/search-by-folder-name-b203` (PR #40 → `feature/1.8.0`)

## Current focus

1. **Search by folder name** — separate **Folder names** Options toggle (independent of File names; both default on). Also fix remaining Windows CI (`SIGKILL` in `checks.py`).

## Touched this session

- Added `SearchOptions.search_folders` + GUI `optFolders` / TUI `#so-folders` / CLI `--folders`/`--no-folders`.
- Walker: `include_directories=search_folders`.
- Fixed Windows `signal.SIGKILL` AttributeError in quality gate interrupt path.
- Local gate `core,gui,tui` PASSED.

## Next steps

1. Push; confirm PR #40 CI green (esp. `test-windows`).
2. Daniel: reopen Options — should see File names + Folder names both ticked.
3. TSM `com.apple.tsm.uiserver` CFMessagePort warnings on macOS GUI launch are harmless IME noise — ignore.
