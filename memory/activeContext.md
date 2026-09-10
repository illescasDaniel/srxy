# Active Context

_Last updated: 2026-09-10_

## Branch

- `develop` — macOS Srxy.app Liquid Glass fix merged from `cursor/61a81fe5` (mdvs).

## Current focus

Installed Srxy.app “old macOS look”: Mach-O launcher + copy/`vtool` SDK 26 restamp on `SrxyPython` so AppKit draws Tahoe chrome (matches `uv run task gui`).

## Just changed

- Applied `/apply-worktree-srxy` from `cursor/61a81fe5`: embed copied `SrxyPython`, restamp sdk 26.0, Mach-O `SrxyAppLauncher`, repair script, dialog/style harden, tests.
- Prefix already repaired from mdvs (`SrxyPython` sdk 26.0; uv CPython remains sdk 15.5).

## Next steps

1. User: visually confirm `open ~/Applications/srxy/Srxy.app` matches `uv run task gui`.
2. Push develop when desired.
3. `/delete-worktree-srxy` for mdvs when no longer needed.
