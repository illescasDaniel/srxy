# Active Context

_Last updated: 2026-09-11_

## Branch

- `main` — v1.7.0 released (`2c64f08`, tag `v1.7.0`).
- `develop` — packaging trunk; sync from `main` after memory hygiene PR merges (pending Daniel OK).
- `feature/1.8.0` — active 1.8.0 release train (OCR, media preview, folder search, GUI Ideas, NSIS, etc.).

## Current focus

1. Memory/release hygiene for v1.7.0 (this PR): collapse shipped Done into release notes; keep progress lean.
2. 1.8.0 train on `feature/1.8.0` — Product/Design/Dev as already briefed; no kickoff without Daniel OK where required.

## Just changed

- v1.7.0 tagged and installers published.
- `memory/progress.md` no longer carries the full 1.7.0 Done dump (see GitHub Release).

## Next steps

1. Merge this memory PR when Daniel gives explicit OK on that PR.
2. Sync `main` → `develop` (separate merge OK).
3. PATCH v1.7.0 release body with changelog (no retag/rebuild).
