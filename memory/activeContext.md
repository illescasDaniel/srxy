# Active Context

_Last updated: 2026-09-11_

## Branch

- `main` @ `fff4427` — v1.7.0 + #49 hotfix + README Linux screenshot update.
- `develop` @ `38c2466` — `main` merged in (ahead of `origin/develop` by 6).
- `feature/1.8.0` — active 1.8.0 release train (OCR, media preview, folder search, GUI Ideas, NSIS, etc.).

## Current focus

Post-merge on `develop`: screenshot + installer workflow updates from `main` are in; memory reconciled.

## Just changed

- Merged `main` → `develop` (`38c2466`): `scripts/docs/export_gui_screenshot.sh`, `docs/images/gui-linux.png`, README, installer workflow `action-gh-release` bumps.
- Resolved memory conflicts: kept develop's #49 sync note; added main's Docs screenshot checklist.
- #49 Windows Property Store isolation already on develop via #50 (`8990f7d`).

## Next steps

1. Push `develop` when ready (`git push`).
2. Optional: re-run `./scripts/docs/export_gui_screenshot.sh` on a real Linux display (no composite); regenerate macOS/Windows tiles on those hosts.
3. Continue 1.8.0 work off `feature/1.8.0`.
