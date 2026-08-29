# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — fixes and improvements for v1.6.6.

## Current focus

None active — AccentButton binding-loop fix merged; Search-after-cancel accent fix already on branch. Gate clean.

## Done this session

- Fixed `AccentButton` `foreground` binding loop via sibling `SystemPalette` (no `control.palette` reads while writing `palette.buttonText`).
- Merged worktree fix into `feature/fixes_1.6.6`; user confirmed binding loop gone.

## Next steps

1. Remaining Final QA: Windows/macOS installers.
2. Release when Final QA is green.
