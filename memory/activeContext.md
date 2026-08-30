# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Just applied worktree `cursor/08e18461` (Search button label + icon colour matches dialog OK).

## Current focus

Applied: **Search button label + icon colour now matches the dialogs' OK button**. Material/Fluent/Universal paint their own highlighted label colour and ignore `palette.buttonText`; the Search button had been hand-tinting a custom `contentItem` from WCAG `foreground` (black on `#3daee9`). Search now uses the style's `IconLabel`; `icon.color` is assigned only on macOS.

## Touched (this apply)

- `src/srxy/adapters/inbound/shared/qml/SrxyControls/AccentButton.qml`
- `src/srxy/adapters/inbound/gui/qml/Main.qml`
- `tests/gui/test_gui_qml_load.py`
- `AGENTS.md`, `memory/*`

## Verified

- Worktree commit `7ca155a`; parent fast-forward `ded25c2..7ca155a`.
- Offscreen probe (Linux Material): Search label + glyph + OK label all `#ffffff` when accented.
- Parent `./scripts/quality/checks.sh --quiet --fix` then `--quiet` **PASSED**.

## Next steps

1. User visual check on Linux (light + dark) that Search text/icon now match OK.
2. Windows (Fluent) and macOS (Aqua) visual check — macOS is the only platform still setting `icon.color` explicitly.
3. `/delete-worktree-srxy` for `cursor/08e18461` (`rlni`) when ready.
4. Manual Windows (and other) installer verification for 1.7.0.
