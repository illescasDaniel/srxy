# Active Context

_Last updated: 2026-09-01_

## Branch

- Worktree `fwvd` on `develop` — dialog UX + Wayland stability.

## Current focus

Dialog UX, reset copy, and Wayland rendering stability — **done**.

## Implemented

- i18n: `Reset app settings…` menu label; friendlier cache/settings confirm copy (EN/ES).
- Settings confirm: action-specific titles + Cancel / Delete|Reset|Download buttons (`settings_confirm_ui`, controller properties, QML).
- Download confirm + update prompt + installer unsafe-prefix dialog: Cancel + action footers.
- Wayland: `prefer_stable_wayland_rendering()` — Vulkan when loader available, else `QSG_RENDER_LOOP=basic` (GUI + installer).
- Tests: `test_qt_theme_wayland.py`, `test_settings_confirm_ui.py`; GUI snapshot updated.
- Docs: Wayland troubleshooting in `docs/development.md`.

## Verified

- `checks.sh --quiet --fix --scope=core,gui --no-cache` PASSED (959 tests).

## Next steps

1. Manual QA on Wayland: `uv run task gui` — confirm no EGL freeze; Settings → Reset Cache / Reset app settings dialogs read well.
2. Carry forward open manual QA items in `progress.md` when ready.
