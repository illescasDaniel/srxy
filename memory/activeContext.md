# Active Context

_Last updated: 2026-10-03_

## Branch

- Working branch: `cursor/macos-sdk26-offline-pyside-8bf8` → PR into `feature/1.8.0` (draft; do not merge).

## Current focus

1. **Offline installer wrapper Liquid Glass** — done locally: `build-offline.sh` restamps in-bundle Python to SDK 26; smoke asserts it; rebuild + `smoke-offline.sh` green. `build-dmg.sh` uses `diskutil image` (APFS headroom 1.5×+64 MiB); no hdiutil deprecation warnings.
2. **`uv run` GUI** — still legacy Aqua with uv-managed CPython (`sdk 15.5`). Not restamping shared host uv Python; use Homebrew/`Python.app` (sdk 26) if Liquid Glass is needed for day-to-day `uv run`.

## Next steps

1. Commit; push / refresh draft PR if desired.
2. Visual open of the rebuilt offline installer `.app` to confirm Liquid Glass chrome.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
