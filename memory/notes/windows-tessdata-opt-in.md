---
name: windows-tessdata-opt-in
description: Ship language packs as opt-in downloads from pinned upstream HTTPS sources; no bundled third-party runtime binaries.
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Windows OCR language data for the installer.
- **Decision:** Ship language packs as opt-in downloads from pinned upstream HTTPS sources; no bundled third-party runtime binaries.
- **Rationale:** Third-party binary policy (`AGENTS.md`) — keep tesseract/ffmpeg/CUDA etc. out of installer artifacts, the repo, and Releases.
