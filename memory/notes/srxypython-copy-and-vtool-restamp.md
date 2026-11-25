---
name: srxypython-copy-and-vtool-restamp
description: Always shutil.copy2 the venv interpreter into Contents/MacOS/SrxyPython (never hardlink — vtool must not mutate ~/.local/share/uv/python); xcrun vtool…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** After Mach-O ``Srxy.app`` + in-bundle ``SrxyPython``, ``NSBundle.mainBundle`` was correct (``com.srxy.app``) but the installed GUI still looked like legacy Aqua vs ``uv run task gui``. Measured: after ``execv`` the process image is uv’s CPython with ``LC_BUILD_VERSION sdk 15.5``; Homebrew ``Python.app`` used by ``uv run`` is ``sdk 26.4``. AppKit enables Tahoe Liquid Glass from the main executable’s linked SDK ([cpython#139404](https://github.com/python/cpython/issues/139404)).
- **Decision:** Always ``shutil.copy2`` the venv interpreter into ``Contents/MacOS/SrxyPython`` (never hardlink — ``vtool`` must not mutate ``~/.local/share/uv/python``); ``xcrun vtool -set-build-version macos 12.0 26.0 -replace``; ad-hoc ``codesign`` the copy and the Mach-O stub. Repair script asserts ``sdk 26``; unit tests cover restamp + embed.
- **Rationale:** Bundle identity alone cannot unlock Liquid Glass; restamping the *exec’d* interpreter matches AppKit’s linked-on-or-after check without switching the prefix off uv-managed CPython.
