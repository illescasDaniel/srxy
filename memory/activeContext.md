# Active Context

_Last updated: 2026-09-10_

## Branch

- `cursor/61a81fe5` (worktree `mdvs`) — macOS GUI + Srxy.app launch + Liquid Glass SDK restamp.

## Current focus

Installed Srxy.app “old macOS look”: copy + `vtool` restamp embedded `SrxyPython` to sdk 26.0.

## Just changed

- [`install.py`](../src/srxy/adapters/inbound/installer/install.py): `_embed_macos_app_python` always copies; `_restamp_macos_linked_sdk` + `_adhoc_codesign_macos`; Mach-O stub also adhoc-signed.
- [`repair-prefix-gui.sh`](../scripts/macos/repair-prefix-gui.sh): assert no hardlink; assert `vtool -show-build` sdk 26.
- [`test_macos_app_launcher.py`](../tests/unit/test_macos_app_launcher.py): restamp + embed sdk 26 tests.
- Prefix repaired: `SrxyPython` sdk 26.0, uv CPython remains sdk 15.5; `open Srxy.app` launched for visual QA.

## Next steps

1. User: visually confirm `Srxy.app` matches `uv run task gui` (Liquid Glass).
2. Port launcher + SDK restamp onto `develop`.
3. Commit when ready.
