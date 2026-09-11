# Progress

_Last updated: 2026-09-11_

## v1.7.0 — shipped 2026-09-11

Shipped on `main` @ `2c64f08` (PR #44 develop→main). Tag/release: https://github.com/illescasDaniel/srxy/releases/tag/v1.7.0

User-facing notes live on the GitHub Release (not duplicated here). Installers (Windows offline zip, macOS offline/online DMG, Linux AppImage) attached to that release; CI tag jobs green.

### Open (post-1.7.0)

- [ ] Optional: Authenticode signing for Windows fat `SrxyInstaller.exe` (SmartScreen).
- [x] Sync #49 hotfix (Windows Property Store subprocess isolation) from `main` @ `182649f` onto `develop` — ported `windows_metadata.py` / `windows_metadata_worker.py` / `tests/unit/test_windows_metadata.py` verbatim via a dedicated sync PR (avoids dirty full main→develop merge from squash history, same pattern as #47/#48). Daniel OK'd this sync; Tech Lead authorized merge.

## Next train — v1.8.0

Active work lives on `feature/1.8.0` (and its topic branches). Track Open items there / Trello 1.8.0 — do not dump 1.8.0 Done into this file until that train ships.
