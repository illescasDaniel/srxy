---
name: offline-installer-sdk-26-restamp
description: (1) In packaging/macos/build-offline.sh, after the relocatable venv resolves, call _restamp_macos_linked_sdk + _adhoc_codesign_macos on the in-bundle…
type: decision
date: 2026-10-03
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** The *installed* `Srxy.app` already gets Liquid Glass via `install.py`'s `vtool` restamp of embedded `SrxyPython`. The offline *installer wizard* `.app` still looked like legacy Aqua: its CFBundleExecutable shell-execs uv-managed CPython copied into `Contents/Resources/python` with `LC_BUILD_VERSION sdk 15.5`. Separately, `build-dmg.sh`'s `hdiutil attach` / `hdiutil convert` print deprecation warnings on macOS 26+ (`diskutil image …` is the replacement). `uv run task gui` also uses uv-managed CPython (`sdk 15.5`); Homebrew Python is `sdk 26.x`.
- **Decision:** (1) In `packaging/macos/build-offline.sh`, after the relocatable venv resolves, call `_restamp_macos_linked_sdk` + `_adhoc_codesign_macos` on the in-bundle interpreter only (never mutate `~/.local/share/uv/python`). Assert `sdk 26` via `vtool`. Add `LSEnvironment.QT_QUICK_CONTROLS_STYLE=macOS` (+ HiDPI keys) to the offline Info.plist. Smoke asserts the restamped SDK. (2) `build-dmg.sh` prefers `diskutil image create blank` / `attach` / `create from --format UDZO` + `diskutil eject`; keep `hdiutil` as fallback when `diskutil image` is unavailable. (3) Do **not** restamp the shared host uv CPython for `uv run` — that would mutate every project’s interpreter; Liquid Glass for day-to-day `uv run` remains a host-toolchain concern (Homebrew/`Python.app` already ships sdk 26).
- **Rationale:** AppKit keys Liquid Glass off the *exec’d* process image’s linked SDK ([cpython#139404](https://github.com/python/cpython/issues/139404)). The offline wrapper already copies Python into the bundle (`UV_LINK_MODE=copy`), so restamping that copy is safe and matches the installed-app fix. DMG styling still needs a RW mount + Finder osa; only the image create/attach/convert/eject verbs move to `diskutil image`.
