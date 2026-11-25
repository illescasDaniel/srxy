---
name: accentbutton-foreground-systempalette
description: Resolve disabled and non-accent face colours from a sibling SystemPalette (refPalette) that we never write to; keep writing palette.buttonText from…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Launching the GUI logged `QML AccentButton: Binding loop detected for property "foreground"` (Search button). `AccentButton` bound `palette.buttonText: control.foreground` while `foreground` read `control.palette.placeholderText` / `control.palette.button` (disabled / non-accent paths). Any write to a palette role dirties the whole group and re-triggers those reads.
- **Decision:** Resolve disabled and non-accent face colours from a sibling `SystemPalette` (`refPalette`) that we never write to; keep writing `palette.buttonText` from `foreground` for macOS/Fusion IconLabels.
- **Rationale:** Breaks the read/write cycle on the same palette object without dropping the `buttonText` override that fixes black labels on Aqua. Existing GUI load test already asserts no binding-loop warnings.
