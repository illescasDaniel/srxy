---
name: linux-material-background
description: On Linux, after follow_system_color_scheme, setdefault QT_QUICK_CONTROLS_MATERIAL_BACKGROUND to #ffffff (light) or #303030 (classic MD2 dark) from…
type: decision
date: 2026-08-27
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Qt 6.11 Material’s default light surface is M3 tonal `#fffbfe` (pinkish white); dark is `#1c1b1f` (purple-grey). Accent was already overridden (portal / palette / Blue) but `ApplicationWindow` and Panes paint `Material.backgroundColor`, so the window still looked pink. A fixed `QT_QUICK_CONTROLS_MATERIAL_BACKGROUND=#ffffff` would lock dark mode to white (env is a single colour, not theme-aware).
- **Decision:** On Linux, after `follow_system_color_scheme`, `setdefault` `QT_QUICK_CONTROLS_MATERIAL_BACKGROUND` to `#ffffff` (light) or `#303030` (classic MD2 dark) from `QStyleHints.colorScheme` / window-palette lightness. User-set env is preserved. Shared QML stays free of Material imports.
- **Rationale:** Neutralises the pink cast on all Material surfaces (window + panes) while still following System light/dark at startup. Env is resolved once (mid-session OS theme toggles still need an app restart for the background role).
