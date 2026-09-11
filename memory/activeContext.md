# Active Context

_Last updated: 2026-09-11_

## Branch

- `main` — v1.7.0 released (`2c64f08`, tag `v1.7.0`); memory hygiene merged @ `2506b53` (#46).
- `develop` — packaging trunk; this PR syncs #46 memory files after squash-based main history blocked a full main→develop merge.
- `feature/1.8.0` — active 1.8.0 release train (OCR, media preview, folder search, GUI Ideas, NSIS, etc.).

## Current focus

1. Keep `memory/` lean post-1.7.0 (release notes on GitHub Release).
2. 1.8.0 train on `feature/1.8.0` — Product/Design/Dev as already briefed; no kickoff without Daniel OK where required.

## Just changed

- v1.7.0 tagged and installers published.
- `memory/progress.md` / `activeContext.md` matched to main after #46.
- Synced #49 hotfix (Windows Property Store subprocess isolation) from `main` @ `182649f` onto `develop`: ported `src/srxy/adapters/outbound/metadata/windows_metadata.py`, `src/srxy/adapters/outbound/metadata/windows_metadata_worker.py` (new), and `tests/unit/test_windows_metadata.py` verbatim (no full main→develop merge, per the #47/#48 squash-history lesson).

## Next steps

1. Continue 1.8.0 work off `feature/1.8.0`.
2. PATCH v1.7.0 release body if not already done (no retag/rebuild).
