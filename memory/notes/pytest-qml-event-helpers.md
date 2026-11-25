---
name: pytest-qml-event-helpers
description: Add tests/gui/helpers.py (load_main, QTest.mouseClick on QQuickItem, set_text, dialog helpers) and given/when/then flows in tests/gui/test_gui_flows.py…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Want UIKit/Selenium-style GUI flows (click buttons, open dialogs, assert results/progress) without a second commercial toolchain.
- **Decision:** Add `tests/gui/helpers.py` (`load_main`, `QTest.mouseClick` on `QQuickItem`, `set_text`, dialog helpers) and given/when/then flows in `tests/gui/test_gui_flows.py` under the existing offscreen **gui** pytest bucket. Prefer typing `pathField` over Browse/`FolderDialog`. Do not adopt Squish or QML `TestCase` files as the primary suite.
- **Rationale:** Fits uv/pytest/CI offscreen gate, mirrors Textual Pilot style, reuses existing `objectName`s; commercial/OS-level drivers are poor ROI for this MIT desktop app.
