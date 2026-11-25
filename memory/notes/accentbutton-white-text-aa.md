---
name: accentbutton-white-text-aa
description: Prefer white text on dark/saturated fills whenever white still clears the WCAG AA 4.5:1 threshold, then fall back to the higher-contrast colour.
type: decision
date: 2026-08-18
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Options dialog OK button (shared `AccentButton`) rendered black text on Windows, unlike Cancel. `contrast_text_on` picked the strictly higher-contrast colour, and for the Windows accent `#0078d4` black wins by a hair (4.637 vs 4.529), producing illegible-looking black-on-blue text.
- **Decision:** Prefer white text on dark/saturated fills whenever white still clears the WCAG AA 4.5:1 threshold, then fall back to the higher-contrast colour.
- **Rationale:** White-on-colour is the CTA convention; the pure max-contrast rule regressed mid-tone accents. Keeps light accents (`#3daee9`, `#90caf9`, `#ffeb3b`) black and dark accents (`#1565c0`) white. Added a regression test for `#0078d4` → white.
