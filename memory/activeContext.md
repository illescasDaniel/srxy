# Active Context

_Last updated: 2026-10-01_

## Branch

- `cursor/search-by-folder-name-b203` (PR #40 → `feature/1.8.0`)
- Release train **`feature/1.8.0`** tip synced in (incl. develop merge / PR #52).

## Current focus

1. **Search by folder name** — finish CI green on PR #40 after base sync.
2. Unlimited OCR / media preview — untouched (#38 / #39).

## Active blockers

- Local `gh` auth is broken (invalid keyring token); CI logs need GitHub web/MCP or re-auth.

## Touched this session

- Merged `origin/feature/1.8.0` into this branch.
- Windows CI suspects after Sep 12 failure (`test-windows` only; unit/cli step):
  - Fixed PowerShell packaging syntax test (`[ref]$null` → real `$errs` var; prefer `pwsh`).
  - Skip bash-only `test_gate_lock_file` on Windows.
  - TUI folder assertions use `Path.name` (not `endswith("/…")`).
  - Bumped `urllib3` 2.7.0 → 2.8.0 (pip-audit CVEs).

## Next steps

1. Push + confirm PR #40 CI (especially `test-windows`) green.
2. Folder-name search — PR review / ready-for-review when CI sticks.
3. Unlimited OCR — Daniel GPU QA; keep draft.
4. Media preview — Daniel smoke; then undraft/merge.
