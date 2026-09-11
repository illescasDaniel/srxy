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
- [x] Confirmed: real Windows CI on PR #49 (https://github.com/illescasDaniel/srxy/pull/49) went green — `test-windows` passed in 2m29s (https://github.com/illescasDaniel/srxy/actions/runs/34580726092/job/103203395479), including the corrupt-JPEG test; all 13 checks passed (`quality`, `test-macos`, `test-windows`, `build*`, security scans).
- [x] Merged to `main` as `182649f` (PR #49).

## Docs — README GUI screenshot (2026-09-11)

- [x] Regenerated `docs/images/gui-linux.png` via `./scripts/docs/export_gui_screenshot.sh`.
- [x] Fixed script for `SrxyControls` import path + theme context props.
- [x] Fixed missing Search / flat Options/Filters: headless Material fills often omit from `grabWindow`; script prefers a real display, falls back to software RHI, and composites button faces from QML props when chrome is missing.
- [ ] Optional: regenerate on a real Linux display (no composite); regenerate `gui-macos.png` / `gui-windows.png` on those hosts; commit when Daniel asks.
