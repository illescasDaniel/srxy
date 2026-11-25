---
name: qt-fallback-picker-reserved-characters
description: Qt 6.11.1's fallback FolderListModel lists the wrong directory for # and literal %20 paths; accepted limitation, backend repair open
type: gotcha
date: 2026-10-24
status: current
supersedes:
superseded_by:
source:
---

The Qt 6.11.1 fallback folder picker (`FolderListModel`) lists the wrong directory when the path contains `#` or a literal `%20`, even though the URL handed to it is correct. A QtWidgets alternative passed 6/6 ad-hoc checks but needs reviewed bootstrap, packaging and UI scope, so no private workaround shipped.

**Why:** the accepted workaround only covers the startup-path patch; the upstream fallback listing defect is independent of srxy's URL conversion (fixed in [kde-browse-url-conversion](kde-browse-url-conversion.md)).

**How to apply:** do not claim reserved-character picker paths work on the fallback backend. Fix it as a reviewed change when the picker is next touched, and cover `#`, literal `%23`/`%20` and Unicode paths in the regression tests.
