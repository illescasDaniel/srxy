---
name: gui-splash-deferred-main
description: (1) Tiny Splash.qml Window with Qt.SplashScreen loaded first; processEvents so it can paint. (2) Defer SearchController / build_app_services / i18n until…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** After import-graph wins, remaining cold-start cost is mostly PySide6 + large `Main.qml`. Users still see a blank gap before the main window. FluentWinUI3 stays; no widgets `QSplashScreen` (app is `QGuiApplication`).
- **Decision:** (1) Tiny `Splash.qml` `Window` with `Qt.SplashScreen` loaded first; `processEvents` so it can paint. (2) Defer `SearchController` / `build_app_services` / i18n until after splash. (3) `Main.qml` starts `visible: false`; Python `_reveal_main` shows it and closes the splash. (4) `QQuickWindow.setDefaultAlphaBuffer(False)` before any Quick window. (5) `SRXY_NO_SPLASH=1` opt-out.
- **Rationale:** Improves perceived launch without changing Fluent chrome; keeps splash out of the widget stack; tests that load Main set `visible: true` themselves.
