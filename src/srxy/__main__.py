"""Package entry point — dispatches to GUI, TUI, or plain CLI."""

from __future__ import annotations

from srxy.adapters.inbound.cli.cli import main


if __name__ == "__main__":
	raise SystemExit(main())
