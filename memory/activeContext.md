# Active Context

_Last updated: 2026-10-03_

## Branch

- Working branch: `cursor/macos-sdk26-offline-pyside-8bf8` → PR into `feature/1.8.0` (draft; do not merge).

## Current focus

1. **Offline installer Finder “(null)”** — fixed: shell `CFBundleExecutable` → Mach-O `SrxyInstallerLauncher.c`. Rebuild + smoke + `open` launched the wizard (`python -m srxy.adapters.inbound.installer`).
2. Prior: SDK-26 restamp of in-bundle Python + `diskutil image` DMG path.

## Next steps

1. Commit; user visually confirms Liquid Glass on the opened installer.
2. Push / refresh draft PR if desired.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
