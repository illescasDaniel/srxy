---
name: accentbutton-native-first
description: AccentButton is now a plain Button with highlighted: control.accent and no custom background/contentItem, so every style renders its native chrome and its…
type: decision
date: 2026-08-19
status: current
supersedes: accentbutton-accent-bool
superseded_by: 
source:
---
- **Context:** `AccentButton` replaced the native button `background`/`contentItem` with a plain `Rectangle`+`Text`, losing Material ripple/elevation, Fluent hover/press states, per-style corner radius, and per-style size (hardcoded 80x32, faked pressed state via `opacity: 0.85`). The prior "explicit `accent` bool + custom fill" workaround existed because `DialogButtonBox` appeared to clobber `highlighted`.
- **Decision:** `AccentButton` is now a plain `Button` with `highlighted: control.accent` and no custom `background`/`contentItem`, so every style renders its native chrome and its own accent. Reading the Qt 6.11 source confirmed `QQuickDialogButtonBoxPrivate::updateLayout()` calls `setHighlighted(button == defaultButton)` on every child each layout pass — so a QML `highlighted` binding is unreliable inside a box, and `buttonRole: AcceptRole` alone does NOT highlight. The fix is `DialogButtonBox.defaultButton` on the primary dialog button (`optionsOkButton`, `filtersOkButton`, `updateYesButton`), which is what actually keeps it highlighted. FluentWinUI3 paints its highlighted fill from `palette.accent` (not `palette.button`/a custom background), so `qt_theme._apply_button_accent_palette` pins `QPalette.Accent` to the resolved button accent.
- **Rationale:** `highlighted` is the native accent on every style in play (Material `Material.accent`, Universal `Universal.accent`, Fluent `palette.accent`, Fusion `palette.highlight`, macOS/Windows native default button), so a custom background is unnecessary and harmful. `foreground` is retained only for the Search button's custom icon+text `contentItem`. Supersedes the 2026-08-18 "`accent` bool, not `highlighted`" entry below.
