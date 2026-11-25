---
name: windows-fat-installer-decision
description: Windows keeps its fat PySide6 installer; no NSIS shell, no Authenticode signing for now
type: decision
date: 2026-11-25
status: current
supersedes:
superseded_by:
source:
---

# Windows installer: keep fat PySide bundle

Windows keeps its fat PySide6 installer (bundled .exe). No NSIS outer shell.
No Authenticode signing for now — SmartScreen warnings are accepted.

**Why:** decision deferred; distribution model works for current user base.
**Rejected:** NSIS outer shell (permissive license), Authenticode signing.
**How to apply:** revisit both in a future release cycle if distribution or trust requirements change.
