---
name: srxy-app-macho-executable-and-dialog-parent
description: Compile packaged SrxyAppLauncher.c to Mach-O at install time (paths baked via -D); still embed SrxyPython. When a sheet is open, set…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Installing with a shell script as `Contents/MacOS/srxy` made LaunchServices fail (`kLSNoExecutableErr` / Dock “(null)”). Separately, help `MessageDialog.parentWindow = open SrxyDialog` raised `Cannot assign QObject* to QWindow*`. InfoButton ToolTip broke after the macOS pill background swap. Tests never clicked “i” with native alerts on.
- **Decision:** Compile packaged `SrxyAppLauncher.c` to Mach-O at install time (paths baked via `-D`); still embed `SrxyPython`. When a sheet is open, set `MessageDialog.parentWindow` to `null` (app-modal NSAlert); otherwise `root`. InfoButton uses HoverHandler-driven ToolTip + objectNames; `capture_qt_messages` fails tests on QML assign/runtime errors; installer tests assert Mach-O magic and LaunchServices open without `kLSNoExecutableErr`.
- **Rationale:** Modern macOS rejects shell `CFBundleExecutable`; `parentWindow` is `QWindow*`; app-modal null stacks above sheets; tests must exercise the user click path.
