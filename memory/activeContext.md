# Active Context

_Last updated: 2026-09-10_

## Branch

- `develop` — Search button magnifier glyph fix applied from `cursor/10ecd083`.

## Current focus

Search magnifier glyph: uniform ring thickness (separate ring + handle paths). Applied to develop.

## Just changed

- [`search.svg`](../src/srxy/adapters/inbound/gui/qml/images/search.svg): separate evenodd ring + SE handle (uniform L=R thickness, 2px margins).
- [`copy-venv.sh`](../.cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv.sh): BSD/macOS rsync `--progress` fallback.
- Applied via `/apply-worktree-srxy` (FF `9ec8dea` onto develop).

## Next steps

1. Push develop when desired.
2. `/delete-worktree-srxy` when the isolated checkout is no longer needed.
