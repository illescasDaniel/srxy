---
name: gui-app-launch-intent
description: Approved architecture uses hidden --app-launch on app entrypoints and preserves path omission until GUI initialization. Ordinary command shims remain…
type: decision
date: 2026-10-23
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Terminal GUI searches should start at caller cwd while installed desktop/Start menu/Finder launches start at home; explicit paths must retain precedence.
- **Decision:** Approved architecture uses hidden `--app-launch` on app entrypoints and preserves path omission until GUI initialization. Ordinary command shims remain unmarked; startup defaults are not reapplied to edits or restored paths. Ignore pickers derive their start URL from the live root on every opening and retain outside-root rejection.
- **Rationale:** Explicit intent avoids TTY/cwd heuristics and inherited environment markers; separating initialization from later path handling preserves user choices.

_Log of significant technical, structural, or dependency choices. Newest first._
