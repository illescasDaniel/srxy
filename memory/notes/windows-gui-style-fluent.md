---
name: windows-gui-style-fluent
description: Use FluentWinUI3 on Windows, fallback Universal → Windows; follow OS light/dark. Results-pane SplitView falls back to Fusion until Fluent styles that…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Plain `Windows` Quick style looked dated and mixed poorly with dark mode.
- **Decision:** Use FluentWinUI3 on Windows, fallback Universal → Windows; follow OS light/dark. Results-pane `SplitView` falls back to Fusion until Fluent styles that control.
- **Rationale:** Native WinUI-like appearance with a safe fallback chain; documented hard-won pitfalls in `AGENTS.md`.
