---
name: macos-accent-labels-white
description: (1) AccentButton sets palette.buttonText: control.foreground so macOS/Fusion labels follow onAccent. (2) SrxyTheme on darwin always uses white onAccent…
type: decision
date: 2026-08-27
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** On macOS the Search button looked misaligned (forced to TextField height ~24px while the native Aqua button is 32px), and accent OK/Search/Launch labels were black on the blue bevel. Qt's macOS `DefaultButton` IconLabel always paints `palette.buttonText` (black by default) even when `highlighted`. Our WCAG `contrast_text_on` also picked black for the system Highlight `#308cc6` (white ratio ≈3.69 < 4.5 AA). Dropping to "native-only" buttons does not fix the black label — the IconLabel still draws black over the native blue chrome.
- **Decision:** (1) `AccentButton` sets `palette.buttonText: control.foreground` so macOS/Fusion labels follow `onAccent`. (2) `SrxyTheme` on darwin always uses white `onAccent` (Aqua convention), bypassing WCAG for that platform. (3) Search-button stretch-to-field / forced padding / `AlignTop` is gated to Windows via `Binding { when }` + `restoreMode`; macOS/Linux keep native size and `AlignVCenter`.
- **Rationale:** Matches Aqua default-button look (white on blue) without custom chrome; Windows Fluent stretch-to-field look is preserved. Regression: platform-aware layout test, OK-button `palette.buttonText == onAccent`, darwin `onAccent` unit test. Gate passed.
