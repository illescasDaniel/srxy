"""Desktop install / uninstall wizard (Linux AppImage first; macOS/Windows later)."""

from __future__ import annotations

from srxy.adapters.inbound.installer.app import run_installer


__all__ = ["run_installer"]
