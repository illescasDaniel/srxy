---
name: linux-native-file-dialogs
description: Add prefer_native_file_dialogs() in qt_theme.py that sets QT_QPA_PLATFORMTHEME=xdgdesktopportal (via os.environ.setdefault, Linux only), and call it in…
type: decision
date: 2026-08-19
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** The GUI/installer "Browse" button uses Qt Quick's `FolderDialog`. On macOS and Windows that dialog is native, but on Linux Qt only renders a native dialog when the platform theme provides one — the KDE/GNOME themes Qt auto-selects do not, so the "Browse" button showed the Qt Quick (non-native) fallback instead of KDE's native folder picker.
- **Decision:** Add `prefer_native_file_dialogs()` in `qt_theme.py` that sets `QT_QPA_PLATFORMTHEME=xdgdesktopportal` (via `os.environ.setdefault`, Linux only), and call it in `gui/app.py` / `installer/app.py` **before** `QGuiApplication` is constructed. The `xdgdesktopportal` platform theme is bundled with PySide6 and serves file dialogs through `org.freedesktop.portal.FileChooser`, which opens the desktop's native picker.
- **Rationale:** Standard freedesktop route, no new dependencies, no bundled binaries; a user-set `QT_QPA_PLATFORMTHEME` is preserved. macOS/Windows are untouched (their dialogs are already native). Fails gracefully to the non-native dialog if the portal is unavailable.
