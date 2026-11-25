---
name: accentbutton-icons-follow-style-colour
description: (1) Drop the Search button's custom contentItem/ColorOverlay (and the now-unused Qt5Compat.GraphicalEffects import in Main.qml); use plain text +…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** On Linux/Material the Options dialog OK button drew white text while the Search button drew a black label *and* a black magnifier glyph. Material/Fluent/Universal compute their own highlighted label colour (`Material.primaryHighlightedTextColor`) and ignore `palette.buttonText`, so our WCAG `contrast_text_on(#3daee9) == #000000` only reached the Search button — which replaced its `contentItem` with a hand-tinted `Row { ColorOverlay; Text }`.
- **Decision:** (1) Drop the Search button's custom `contentItem`/`ColorOverlay` (and the now-unused `Qt5Compat.GraphicalEffects` import in `Main.qml`); use plain `text` + `icon.source` so the style's own `IconLabel` paints both. (2) `AccentButton` also pins `palette.brightText: foreground`, because Fusion/Basic tint icons from `brightText` while drawing the label from `buttonText`. (3) `icon.color` is assigned **only** on macOS, via `Binding { when: Qt.platform.os === "osx" }` — Aqua predates `defaultIconColor`, but on every other style the role must stay *unresolved*: `QQuickIconLabel` falls back to `defaultIconColor` only when `icon.color` was never set, so even `"transparent"` strands the glyph untinted.
- **Rationale:** Matching the style beats out-computing it — the OK button was already the style's own colour, so the only way for Search to agree was to stop overriding. Reading the painted colour back (`contentItem.color`) was tried and rejected: `QQuickIconLabel::color` is non-bindable, so the value froze at creation. Also removes a latent packaging bug — both `packaging/macos/prune-pyside.sh` and `packaging/linux-appimage/prune_pyside.sh` already delete the `Qt5Compat` QML module that `Main.qml` imported. Regression test asserts the Search label, its `QQuickIconImage` tint, and the dialog OK label are all the same colour.
