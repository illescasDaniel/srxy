---
name: path-drop-window-filter
description: (1) Size pathDropTarget from pathRow.implicitHeight (row uses width: parent.width, not mutual fill). (2) Install PathDropWindowFilter on the main…
type: decision
date: 2026-10-01
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** After stacking `DropArea` above the path row, macOS Finder still showed no green ``+`` and did not update the path. The Where GroupBox also lost its gap before What/How. Root cause: RowLayout + DropArea both `anchors.fill` collapsed the GroupBox `contentItem` height on Aqua (tiny/zero drop target), and QML `DropArea` alone often never accepts Finder drags into a Quick Controls window.
- **Decision:** (1) Size `pathDropTarget` from `pathRow.implicitHeight` (row uses `width: parent.width`, not mutual fill). (2) Install `PathDropWindowFilter` on the main `QQuickWindow` (production `app.py` + test `load_main`) to accept `DragEnter`/`DragMove`/`Drop` over `pathDropTarget`, set `controller.pathDropHover`, and call `handleDroppedPathUrls`. Keep QML `DropArea` as a non-macOS fallback; chrome binds to `containsDrag || pathDropHover`.
- **Rationale:** Window-level acceptance is what Finder needs for the ``+`` cursor; explicit content height restores section spacing. One hit-test item (`pathDropTarget`) shared by filter and DropArea avoids divergent zones.

- **Context:** PR #41 drag-and-drop onto **Where to search** looked correct in QML but Finder drops on macOS did nothing (no highlight, path unchanged). The `DropArea` was declared *under* the Browse/`TextField` row; Qt delivers OS drag events to the highest-z target under the cursor, and native `TextField` accepts drops, so it stole Finder events.
- **Decision:** Keep the path controls as a `pathRow`, then overlay `pathDropArea` with `z: 1` (highlight/outline/label as DropArea children). DropArea does not accept mouse buttons, so Browse clicks and typing still reach the controls. Regression: `test_given_path_drop_area_when_loaded_then_stacked_above_path_row` asserts `pathDropArea.z > pathRow.z` and that Browse remains clickable.
- **Rationale:** Matches Qt’s drag hit-testing (higher z wins) without disabling the native text field or requiring platform-specific QML. Same layout on Linux/Windows, where the under-sibling bug was easier to miss. **Superseded in part** by the window-filter decision above when z-order alone proved insufficient on macOS.
