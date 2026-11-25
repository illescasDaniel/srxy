---
name: qt-theme-selection-in-python
description: Keep platform style choice in src/srxy/adapters/inbound/gui/qt_theme.py (apply_qt_quick_theme); never import QtQuick.Controls.<Style> in shared QML.
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Style imports in shared QML forced a single chrome and broke native macOS controls.
- **Decision:** Keep platform style choice in `src/srxy/adapters/inbound/gui/qt_theme.py` (`apply_qt_quick_theme`); never `import QtQuick.Controls.<Style>` in shared QML.
- **Rationale:** macOS needs native Aqua; Linux uses Material (Dense); Windows uses FluentWinUI3. Platform-specific attached properties belong only in platform-private QML, or avoided.
