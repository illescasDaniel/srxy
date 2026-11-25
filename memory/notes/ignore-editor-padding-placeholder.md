---
name: ignore-editor-padding-placeholder
description: Keep the existing TextArea and controller interface, explicitly set padding/insets and top alignment, and render a stationary placeholder in the…
type: decision
date: 2026-10-23
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** The GUI ignore editor's custom Rectangle background removed Material's implicit background height while retaining height-dependent text padding and a floating placeholder; Fluent also defaults to vertical centering.
- **Decision:** Keep the existing TextArea and controller interface, explicitly set padding/insets and top alignment, and render a stationary placeholder in the background only when entered and IME preedit text are empty. Extend the existing ignore-rules spec and plan rather than creating a separate feature spec.
- **Rationale:** Owning the local editor geometry prevents style-dependent overlap without forcing a platform style or changing search behavior; a single spec keeps the existing feature's requirements together. Wireframe, spec amendment and architecture approved in chat on 2026-10-23.
