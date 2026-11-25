---
name: fresh-folder-picker-per-open
description: Create a fresh ignore folder dialog for each click, set parentWindow: root and the live-root currentFolder, and defer destruction after…
type: decision
date: 2026-10-23
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Qt 6.11's FolderDialog applies its initial directory only on first show; a reused dialog ignored root changes. A dynamically created dialog also needed an explicit window parent to become visible.
- **Decision:** Create a fresh ignore folder dialog for each click, set `parentWindow: root` and the live-root `currentFolder`, and defer destruction after acceptance/rejection. Keep the working reusable file dialog.
- **Rationale:** This preserves the approved repeated-opening behavior and normal native dialog presentation; real-QML regression tests exercise changed roots, navigation, acceptance and cancellation.
