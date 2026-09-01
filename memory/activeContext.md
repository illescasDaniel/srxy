# Active Context

_Last updated: 2026-09-01_

## Branch

- Worktree `ipvq` on `develop`.

## Current focus

Secondary dialog / toolbar button styling — Cancel matches Options/Filter on Linux Material.

## Implemented

- `SecondaryButton` — contained neutral CTA (`flat: false`, body-text foreground).
- `SrxyDialogFooter` — replaces `DialogButtonBox` footers (avoids Material accent foreground on Cancel).
- GUI + installer: Options/Filter/Browse/Cancel/nav + all dialog footers migrated.

## Verified

- `checks.sh --quiet --fix --scope=gui --no-cache` PASSED (214 gui tests).

## Next steps

1. Manual QA on Linux Material: open Options dialog — Cancel should match Options button (gray fill, neutral text).
2. Spot-check Windows Fluent and macOS native dialog footers.
