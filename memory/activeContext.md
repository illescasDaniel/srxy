# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Just applied worktree `cursor/79bcea9a` (Magika/preview + GUI search responsiveness + spinner/progress + preview scrollbar).

## Current focus

Worktree `rlni` (venv copied from primary). Just finished: **Search button label + icon colour now matches the dialogs' OK button**. Root cause was that Material/Fluent/Universal paint their own highlighted label colour and ignore `palette.buttonText`, while the Search button hand-tinted a custom `contentItem` from `AccentButton.foreground` (WCAG `onAccent`, which was black for accent `#3daee9`).

## Touched (this change)

- `src/srxy/adapters/inbound/shared/qml/SrxyControls/AccentButton.qml` — added `palette.brightText: foreground` (Fusion/Basic tint icons from `brightText`); `icon.color` now assigned only on macOS via `Binding { when: … "osx" }`.
- `src/srxy/adapters/inbound/gui/qml/Main.qml` — Search button uses plain `text` + `icon.source`; removed the `Row { ColorOverlay; Text }` `contentItem`, `useNativeIconLabel`, and the `Qt5Compat.GraphicalEffects` import.
- `tests/gui/test_gui_qml_load.py` — new regression test comparing Search label, its `QQuickIconImage` tint, and the Options OK label.
- `AGENTS.md`, `memory/*`.

## Verified

- Offscreen probe (Linux Material, accent `#3daee9`): Search label + glyph + OK label all `#ffffff` when accented, all `#000000` when not; on-screen render confirms a white magnifier on the blue pill.
- Regression test fails (`['#000000'] == ['#ffffff']`) when `icon.color` is assigned off-macOS.
- `./scripts/quality/checks.sh --quiet --fix --scope=core,gui` **PASSED** (191 gui + 686 core).

## Next steps

1. User visual check on Linux (light + dark) that Search text/icon now match OK.
2. Windows (Fluent) and macOS (Aqua) visual check — macOS is the only platform still setting `icon.color` explicitly.
3. `/apply-worktree-srxy` when satisfied.
4. Manual Windows (and other) installer verification for 1.7.0.
