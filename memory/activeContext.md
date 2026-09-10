# Active Context

_Last updated: 2026-09-10_

## Branch

- `cursor/10ecd083` off `develop` — Search button icon clip fix.

## Current focus

Search magnifier glyph: uniform ring thickness (separate ring + handle paths).

## Just changed

- [`search.svg`](../src/srxy/adapters/inbound/gui/qml/images/search.svg): split into evenodd ring (`Ro=5`/`Ri=3` at `(7,7)`) + separate rounded handle path. Compound outline had made the right/SE rim thicker under AA (measured L≈0.94 vs R≈1.56 px); now L=R=2.12 px, margins 2 all around.
- Prior: SE handle restore, recenter after left clip, copy-venv BSD rsync, worktree `.venv`.

## Next steps

1. User visual confirm in live macOS GUI.
2. Commit when asked.
