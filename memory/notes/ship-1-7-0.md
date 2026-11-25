---
name: ship-1-7-0
description: Bump project.version and both min_srxy_version values to 1.7.0 instead of releasing 1.6.6. Document the full bump checklist in docs/development.md…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Branch `feature/fixes_1.6.6` accumulated Fluent/Material/macOS UI work, AccentButton, preview find/highlight, installers, search streaming, and permission-denied skips — more than a patch relative to 1.6.5.
- **Decision:** Bump `project.version` and both `min_srxy_version` values to **1.7.0** instead of releasing 1.6.6. Document the full bump checklist in `docs/development.md` (**Bumping the release version**). Leave `installer_version` at `16` (installer capability stamp unchanged by this renumber alone).
- **Rationale:** Semver minor for user-visible UI/feature scope; online installers should require ≥1.7.0 once that release is on PyPI.
