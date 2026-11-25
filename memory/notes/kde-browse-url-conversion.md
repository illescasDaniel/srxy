---
name: kde-browse-url-conversion
description: The main Browse handler stripped the file:// prefix but retained escaping, so KDE's selected # directory became %23 in the search field and failed…
type: decision
date: 2026-10-24
status: current
supersedes: 
superseded_by: 
source:
---
The main Browse handler stripped the `file://` prefix but retained escaping, so KDE's selected `#` directory became `%23` in the search field and failed validation. Pass the selected `QUrl` directly to a dedicated controller slot and convert with `toLocalFile()` once. Do not decode manually typed native paths: literal `%23` and `%20` names must remain literal. Loaded-QML acceptance followed by real search passes for `#`, literal `%23`, literal `%20` and Unicode. This repairs srxy's acceptance boundary independently of the still-open upstream fallback listing defect.
