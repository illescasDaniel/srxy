# Progress

_Last updated: 2026-09-11_

## v1.7.0 — shipped 2026-09-11

Shipped on `main` @ `2c64f08` (PR #44 develop→main). Tag/release: https://github.com/illescasDaniel/srxy/releases/tag/v1.7.0

User-facing notes live on the GitHub Release (not duplicated here). Installers (Windows offline zip, macOS offline/online DMG, Linux AppImage) attached to that release; CI tag jobs green.

### Open (post-1.7.0)

- [ ] Optional: Authenticode signing for Windows fat `SrxyInstaller.exe` (SmartScreen).

## Next train — v1.8.0

Active work lives on `feature/1.8.0` (and its topic branches). Track Open items there / Trello 1.8.0 — do not dump 1.8.0 Done into this file until that train ships.

## Hotfix — `main` CI #147 test-windows crash (2026-09-11)

Branch `cursor/hotfix-windows-corrupt-jpeg-property-store-cdc4` off `main`. **Merge waits on Daniel's fresh OK on that specific PR — do not merge.** No retag / no v1.7.0 rebuild.

- [x] Root-caused: native `0xc0000002` (STATUS_NOT_IMPLEMENTED) fatal exception in `windows_metadata.py::_open_property_store` -> `propsys.SHGetPropertyStoreFromParsingName`, triggered by the corrupt-JPEG fixture in `test_given_corrupt_jpeg_when_searching_contents_then_skips_gracefully`; confirmed via `gh run view --job 103189783873 --log` against https://github.com/illescasDaniel/srxy/actions/runs/34576418507/job/103189783873.
- [x] Fix: isolate Property Store reads used for content search (`_read_searchable_property_entries`) in a lazily-spawned, reused worker subprocess (`windows_metadata_worker.py`) on real Windows only (`sys.platform == "win32"`); worker crash/hang fails soft to `[]` (same contract as `except OSError: return []`) and respawns for the next call. Direct in-process path (`_read_searchable_property_entries_direct`) kept for the existing mocked cross-platform unit tests.
- [x] Unit coverage added in `tests/unit/test_windows_metadata.py` (dispatch, dead-worker, hung-worker timeout, healthy-worker reuse, worker request handler) — 18/18 passed.
- [x] Local verification: `checks.sh --quiet --all` PASSED (ruff/shell/ty/pip-audit/build/pytest); corrupt-JPEG test passes; full `tests/unit tests/cli` (772 tests) passes.
- [ ] Open: confirm real Windows CI (`test-windows` job on the PR) goes green, including the corrupt-JPEG test — this is the actual regression proof (not reproducible on Linux dev VM).
- [ ] Open: Daniel's fresh OK on the PR, then merge (not part of this agent's scope).
