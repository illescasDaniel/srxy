---
name: macos-quit-signals-and-native-alerts
description: (1) install_terminal_quit_signals always on Unix: un-ignore SIGINT, handlers + signal.set_wakeup_fd + QSocketNotifier + 200ms QTimer pump →…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** (1) Ctrl+C from `uv run task gui` left the Qt window open because `app.exec()` never saw SIGINT — and a TTY-only install skipped some launch trees; background/parent jobs often leave SIGINT as ``SIG_IGN``. (2) Packaged offline installer / installed app could look non-native if the macOS Quick style failed to load silently (Basic/Fusion). (3) Qt’s macOS Quick `Dialog` is Fusion-derived; Options/Filters/etc. looked like old Qt boxes vs WinUI/Material.
- **Decision:** (1) `install_terminal_quit_signals` always on Unix: un-ignore SIGINT, handlers + ``signal.set_wakeup_fd`` + ``QSocketNotifier`` + 200ms ``QTimer`` pump → ``QCoreApplication.quit()``; wired in GUI + installer. (2) `prefer_macos_quick_controls_style` sets `QT_QUICK_CONTROLS_STYLE=macOS` before `QGuiApplication`; Darwin theme path warns if `QQuickStyle.name() != "macOS"`; offline build pins `PySide6==6.11.1`; smoke asserts style; packaging contract tests. (3) Form modals use shared ``SrxyDialog``; on macOS ``+macos/SrxyDialog.qml`` (QFileSelector) is a ``Templates.Dialog`` with sheet-like chrome (radius 14, centered title, dim scrim) — Windows/Linux keep a plain ``Dialog`` passthrough. Simple confirms/help/error use native ``MessageDialog`` (NSAlert) with ``parentWindow`` when not offscreen.
- **Rationale:** Matches Python+Qt best practice for Ctrl+C (wakeup fd + timer); makes packaged style failures visible; Qt has no native form Dialog on macOS, so sheet chrome + NSAlert is the practical native-feeling split without touching other platforms.
