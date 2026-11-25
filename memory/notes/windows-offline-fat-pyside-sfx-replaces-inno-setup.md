---
name: windows-offline-fat-pyside-sfx-replaces-inno-setup
description: Remove Inno Setup packaging (srxy-offline.iss, Inno build-offline.ps1 / smoke-offline.ps1, tessdata-langs.txt, ISS contract tests, Inno CI job/tasks). The…
type: decision
date: 2026-09-07
status: current
supersedes: windows-installer-inno-for-now
superseded_by: 
source:
---
- **Context:** The PySide fat self-extracting `SrxyInstaller.exe` proved clearly better UX than the Inno Setup wizard. Keeping both doubled CI/docs/maintenance cost and left a commercial-license cliff for Inno.
- **Decision:** Remove Inno Setup packaging (`srxy-offline.iss`, Inno `build-offline.ps1` / `smoke-offline.ps1`, tessdata-langs.txt, ISS contract tests, Inno CI job/tasks). The Windows offline artifact is solely the fat PySide zip (`srxy-*-installer-*-x86_64.zip` → `SrxyInstaller.exe`). Release attach uses that artifact. NSIS remains optional future outer packaging, not a prerequisite to ship.
- **Rationale:** One Windows installer stack aligned with macOS/Linux PySide wizards; no Inno commercial license exposure; simpler releases.
