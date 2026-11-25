---
name: search-button-top-pinned-by-query-mode
description: Added searchButton.pinTop: stretchToField || modeBox.currentIndex === 1 and switched Layout.alignment on the Search button and its adjacent…
type: decision
date: 2026-09-12
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** `searchButton.Layout.alignment` was `stretchToField ? Qt.AlignTop : Qt.AlignVCenter`, where `stretchToField` is Windows-only (Fluent look). On macOS/Linux the button used native sizing + `AlignVCenter`, which is fine for the single-line simple/advanced query modes but re-centres Search vertically as the multi-term list (`multiTermColumn`) grows taller — Trello `yO4X6JDM` wants Search pinned to its initial (single-term) y regardless of platform.
- **Decision:** Added `searchButton.pinTop: stretchToField || modeBox.currentIndex === 1` and switched `Layout.alignment` on the Search button and its adjacent query-issue/search-warnings `ToolButton`s to `pinTop`. Left simple/advanced-query behaviour (native centred sizing off Windows) unchanged since `pinTop` only forces top for multi-term mode (index 1) or the existing Windows stretch case.
- **Rationale:** Scoping the pin to multi-term mode (rather than always `AlignTop` everywhere) preserves the intentional macOS/Linux native vertical centring for the common single-field simple/advanced modes, while satisfying the specific multi-term growth requirement. Geometry regression test (`mapToScene` y comparison across 1→6→1 terms) added instead of a screenshot assertion per acceptance criteria.
