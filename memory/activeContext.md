# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — main checkout; preview font fix committed after apply-worktree + gate.

## Current focus

None active — preview HTML font-family fix on parent branch; gate clean.

## Done this session

- Applied worktree `r9oj` preview font fix; `checks-win` fix+verify PASSED; committed on `feature/fixes_1.6.6`.

## Next steps

1. Manual verify: reopen multi-script preview files under `uv run task gui` — expect no `8514oem` / `Fixedsys` / DirectWrite lines.
2. Final QA: Windows/macOS installers; release when green.
3. `/delete-worktree` for `r9oj` when finished with the isolated checkout.
