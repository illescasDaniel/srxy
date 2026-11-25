---
name: accentbutton-accent-bool
description: Give AccentButton its own property bool accent: true and drive fillColor/foreground off that; the Search button's dynamic stale toggle now binds accent…
type: decision
date: 2026-08-18
status: superseded
supersedes: 
superseded_by: accentbutton-native-first
source:
---
- **Context:** In dark mode the Search Options / Filters OK buttons (and update "Yes") rendered dark instead of accent-filled. `AccentButton` chose accent vs. secondary fill by reading the standard `highlighted` property, but `DialogButtonBox` (FluentWinUI3, and Material/Fusion/Universal alike) forcibly overrides `highlighted` on its child buttons from its own delegate, so the `highlighted: true` set inside `AccentButton` was silently dropped and `fillColor`/`foreground` fell back to `palette.button` (5.8%-alpha white in Fluent dark mode). `buttonRole: AcceptRole` and overriding `DialogButtonBox.delegate` did not restore it.
- **Decision:** Give `AccentButton` its own `property bool accent: true` and drive `fillColor`/`foreground` off that; the Search button's dynamic stale toggle now binds `accent` instead of `highlighted`.
- **Rationale:** `highlighted` is a container-managed property (`Container`/`DialogButtonBox` re-assign it), so it cannot be trusted to express "is the primary CTA". A dedicated `accent` flag is unambiguous and immune to `DialogButtonBox`. Added `optionsOkButton`/`filtersOkButton` objectNames plus a regression test asserting the OK buttons render `fillColor == accent` / `foreground == onAccent`.
