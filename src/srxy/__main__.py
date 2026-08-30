"""Package entry point — dispatches to GUI, TUI, or plain CLI."""

from __future__ import annotations

from srxy.application.startup_timing import begin, mark


begin()
from srxy.adapters.inbound.cli.cli import main  # noqa: E402


mark("cli_imported")


if __name__ == "__main__":
	raise SystemExit(main())
