---
name: help-alerts-use-srxydialog
description: Help/unavailable always open helpDialog (SrxyDialog + AccentButton). When another sheet is open, force Popup.Window so help sits above Options; otherwise…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Info-button help used Qt Quick ``MessageDialog``. On macOS it fell back to Basic chrome (weird OK) and, with ``parentWindow`` null/root under ``Popup.Native`` Options, stacked *behind* the Options sheet so OK was almost unclickable.
- **Decision:** Help/unavailable always open ``helpDialog`` (``SrxyDialog`` + ``AccentButton``). When another sheet is open, force ``Popup.Window`` so help sits above Options; otherwise ``Popup.Native`` / Item for tests. Remove remaining MessageDialog error/confirm paths in Main.qml (same stacking/chrome issues).
- **Rationale:** AccentButton matches Options/Filters; Window-above-sheet is reliable where Native-on-Native and NSAlert parenting are not.
