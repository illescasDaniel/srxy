---
name: offline-payload-wheel-and-macos-dialog
description: (1) When APPDIR / SRXY_INSTALLER_PAYLOAD has a wheel, resolve_srxy_install_spec always returns that path (no PyPI upgrade). (2) macOS…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Local installer wizard looked correct (live tree) while `~/Applications/srxy` stayed on an older install (Fusion `Dialog`, no `+macos` sheet). Separately, packaged offline installers could prefer a newer PyPI `srxy` than the wheel they shipped. Custom sheet chrome with stacked fake shadows still felt non-native. On macOS 26, `iconutil -c icns` rejects valid iconsets (`Invalid Iconset`), breaking launcher tests and `.app` icon generation.
- **Decision:** (1) When `APPDIR` / `SRXY_INSTALLER_PAYLOAD` has a wheel, `resolve_srxy_install_spec` always returns that path (no PyPI upgrade). (2) macOS `+macos/SrxyDialog.qml` uses `Popup.Native` for interactive runs; offscreen tests keep `Popup.Item` when `srxyUseNativeAlerts === false`. Drop double drop-shadow rectangles; footer gets a hairline only. (3) Pack `.icns` via `srxy.resources.icons.icns.write_icns_from_png` (Pillow + PNG ICNS chunks); use it from `install.py` and macOS packaging `build_icns`.
- **Rationale:** Wizard UI and installed package must match the payload; Cocoa-hosted popups beat hand-drawn Fusion sheets; tests need overlay Item popups for `findChild` / synthetic clicks; Apple’s encoder is broken on Tahoe while a pure-Python ICNS still round-trips through `iconutil --convert iconset`.
