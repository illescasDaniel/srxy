---
name: offline-installer-macho-executable
description: Add relocatable SrxyInstallerLauncher.c (resolves Contents via _NSGetExecutablePath, sets APPDIR / PYTHONNOUSERSITE, execvs Resources/venv/bin/python -m…
type: decision
date: 2026-10-03
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** After SDK-26 restamp, double-clicking the offline installer still failed with Finder “does not have permission to open “(null).”” — the same `kLSNoExecutableErr` / Dock “(null)” failure `Srxy.app` hit when its executable was a shell script.
- **Decision:** Add relocatable `SrxyInstallerLauncher.c` (resolves `Contents` via `_NSGetExecutablePath`, sets `APPDIR` / `PYTHONNOUSERSITE`, `execv`s `Resources/venv/bin/python -m srxy.adapters.inbound.installer`). `build-offline.sh` compiles it with `clang` + ad-hoc `codesign` as `Contents/MacOS/srxy-installer-offline`. Smoke rejects a `#!` shebang / requires Mach-O.
- **Rationale:** Modern macOS LaunchServices will not treat a shell script as `CFBundleExecutable`. Paths stay relative so the `.app` remains relocatable (unlike the prefix-baked `SrxyAppLauncher.c`).
