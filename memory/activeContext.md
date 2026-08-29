# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — fixes and improvements for v1.6.6.

## Current focus

None active — Search-after-cancel accent fix committed and pushed. Gate clean; visually confirmed on Windows.

## Done this session

- Windows dark-mode GUI visual QA confirmed OK by user.
- Fixed Search button dark tint after cancel: only commit `_last_snapshot` on successful finish; clear baseline on cancel/error so `stale`/accent stay on.
- Unit + QML regression tests; `checks-win` fix+verify PASSED; user visual re-check OK.

## Next steps

1. Remaining Final QA: Windows/macOS installers.
2. Release when Final QA is green.
