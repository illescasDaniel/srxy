# Active Context

_Last updated: 2026-08-27_

## Branch

- `feature/fixes_1.6.6` — fixes and improvements for v1.6.6.
- In sync with `origin/feature/fixes_1.6.6`. Working tree clean.

## Current focus

None active — Linux Material background + macOS Search/OK theme fixes are committed and visually tested. Remaining work is Final QA (Windows dark mode / installers).

## Done this session (committed + tested)

### Linux Material pinkish background — `8216a59`

- Qt 6.11 Material default light surface `#fffbfe` (pinkish); dark `#1c1b1f`.
- `qt_theme.py`: after `follow_system_color_scheme` on Linux, `setdefault` `QT_QUICK_CONTROLS_MATERIAL_BACKGROUND` to `#ffffff` / `#303030` from colour scheme.
- Tests: light/dark/preset/linux-apply coverage in `test_qt_theme.py`.
- Visually confirmed light/dark on Linux.

### macOS Search alignment + accent labels — `4f3b8e2`, `a3344ed`

- Search stretch-to-field / forced padding only on Windows; macOS/Linux keep native size + `AlignVCenter`.
- `AccentButton` binds `palette.buttonText: foreground`; darwin `SrxyTheme.onAccent` always white (Aqua).
- Visually confirmed on macOS.

## Next steps

1. Final QA: visually check Windows dark mode (incl. results `SplitView` grips) and the Windows/macOS installers.
2. Release when Final QA is green.

## Key recent commits (theme)

- `8216a59` — Linux Material neutral background
- `a3344ed` / `4f3b8e2` — macOS theme / Search+OK fixes
- `d54c86c` — row-based `ResultsModel` + v1.6.6 bump
