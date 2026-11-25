---
name: preserve-explicit-path-traversal
description: Startup anchors explicit relative input without collapsing its components; only exact . is simplified. The picker resolves an existing, accessible…
type: decision
date: 2026-10-24
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Lexically normalizing `link/../target` changes its filesystem target when `link` is a symlink, and can incorrectly make `missing/../target` valid. Qt's own lexical cleanup can repeat that mistake after URL handoff.
- **Decision:** Startup anchors explicit relative input without collapsing its components; only exact `.` is simplified. The picker resolves an existing, accessible directory to its physical path after validation, without changing the main search field.
- **Rationale:** This preserves the caller's requested search target and gives Qt the correct picker directory. Red-first symlink/missing-component and Qt-cleanup regressions pass; startup policy remains free of filesystem I/O.
