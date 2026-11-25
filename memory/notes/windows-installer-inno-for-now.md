---
name: windows-installer-inno-for-now
description: (1) Keep Inno-based Windows builds until revenue warrants a commercial Inno license or migration completes. (2) Planned migration order: PySide offline…
type: decision
date: 2026-09-01
status: superseded
supersedes: 
superseded_by: windows-offline-fat-pyside-sfx-replaces-inno-setup
source:
---
- **Context:** Windows offline installer uses Inno Setup (free for non-commercial use). Paid website bundles may include Mac/Linux installers; Inno commercial license applies when srxy for-profit revenue exceeds ~USD 5k/year (donations count). Currently zero sales.
- **Decision:** (1) Keep Inno-based Windows builds until revenue warrants a commercial Inno license or migration completes. (2) Planned migration order: PySide offline wrapper on Windows (parity with macOS/Linux offline wizards), then replace Inno outer shell with NSIS (permissive license).
- **Rationale:** Aligns Windows with existing PySide installer stack; NSIS avoids Inno commercial licensing for future paid distribution; Inno is acceptable short-term at current revenue.
