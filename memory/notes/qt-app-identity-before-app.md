---
name: qt-app-identity-before-app
description: Add apply_app_identity(name) to app_icon.py that sets QGuiApplication.setApplicationName(name), QGuiApplication.setOrganizationName("srxy"), and…
type: decision
date: 2026-08-19
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** On Linux the GUI logged `qt.qpa.services: Failed to register with host portal QDBusError("org.freedesktop.portal.Error.Failed", "Could not register app ID: Connection already associated with an application ID")` at startup. Qt 6.10+/6.11 `QDesktopUnixServices` registers the app with the xdg-desktop-portal host-app registry (`org.freedesktop.host.portal.Registry.Register`) using `QGuiApplication::desktopFileName()`; the portal requires `Register` to run before any other portal call, and only once. Because identity was set *after* `QGuiApplication` was constructed, `desktopFileName()` was empty at init so Qt deferred registration to a queued callback; by then `follow_system_color_scheme()` (inside `apply_qt_quick_theme`) had already made a portal colour-scheme read, so the connection was already associated and `Register` failed.
- **Decision:** Add `apply_app_identity(name)` to `app_icon.py` that sets `QGuiApplication.setApplicationName(name)`, `QGuiApplication.setOrganizationName("srxy")`, and `apply_desktop_file_name(name)` via the **static** setters, and call it in `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`) **before** `QGuiApplication` is constructed. `apply_desktop_file_name` becomes static-only (`name` arg, no app instance).
- **Rationale:** Qt reads these at init time and registers with the portal immediately, before any other portal method call, so the `Connection already associated` warning disappears. The `.desktop`-file guard (`desktop_file_available`) is preserved so `uv run`/PyPI runs without a desktop entry still skip registration gracefully.
