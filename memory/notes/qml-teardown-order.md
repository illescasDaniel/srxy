---
name: qml-teardown-order
description: After app.exec() returns, destroy root windows first (root.deleteLater()), then engine.deleteLater(), then flush QEvent.Type.DeferredDelete with…
type: decision
date: 2026-08-18
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** GUI and installer exit logged `There are still "1" items in the process of being created at engine destruction.`. `QQmlEnginePrivate::~QQmlEnginePrivate` warns when `inProgressCreations > 0`; at interpreter shutdown the `QQmlApplicationEngine` was destroyed while its `QQuickWindow` (and its async `QQmlDelegateModel`/`Loader` incubators) were still alive.
- **Decision:** After `app.exec()` returns, destroy root windows first (`root.deleteLater()`), then `engine.deleteLater()`, then flush `QEvent.Type.DeferredDelete` with `sendPostedEvents` + `processEvents()` — in both `gui/app.py` and `installer/app.py`.
- **Rationale:** Deleting the window cascades into the delegate model/loader, whose incubator destructors `clear()` and decrement `inProgressCreations` before the engine destructor runs, so the warning is avoided. This is the standard Qt teardown order; deleting the engine first leaves stale PySide wrappers (verified `RuntimeError` in a repro) and the pending-incubator warning.
