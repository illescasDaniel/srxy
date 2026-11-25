---
name: windows-offline-self-extracting-exe
description: Keep the distribution zip name, but put only a self-extracting SrxyInstaller.exe inside. Build appends payload-embed.zip (python/venv/share) plus a…
type: decision
date: 2026-09-06
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** The PySide offline zip previously expanded to a portable folder (`python\` + `venv\` + `share\` + thin `SrxyInstaller.exe`). Users wanted a single fat exe after unzip.
- **Decision:** Keep the distribution zip name, but put only a self-extracting `SrxyInstaller.exe` inside. Build appends `payload-embed.zip` (python/venv/share) plus a `SRXYISFX` trailer (sha256 + length + magic) to a csc-compiled stub. On launch the stub extracts once to `%LOCALAPPDATA%\srxy\is\<sha16>\p\` (short path to stay under MAX_PATH for deep Qt trees) and sets `SRXY_INSTALLER_PAYLOAD` as before. Headless args use `python.exe` + WaitForExit (no MessageBox).
- **Rationale:** Same embedded payload contract as macOS/Linux offline wizards without introducing NSIS yet; unzip UX is one double-clickable exe; cache avoids re-extract on every launch.
